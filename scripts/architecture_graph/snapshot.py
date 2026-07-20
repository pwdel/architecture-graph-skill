from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from architecture_graph.canonical import (
    atomic_write_json,
    canonical_bytes,
    sha256_digest,
    source_revision_digest,
    stable_id,
)
from architecture_graph.jsonl_store import (
    AtomicJsonlLedger,
    get_record,
    iter_records,
    select_records,
    write_records,
)
from architecture_graph.project import ProjectLock, ProjectPaths
from architecture_graph.records import (
    JSONValue,
    RECORD_KIND_BY_TYPE,
    RECORD_TYPES,
    Record,
    finalize_record,
    validate_record,
    validate_record_shape,
)


SNAPSHOT_ID = re.compile(r"^(deterministic|enriched|reviewed):([0-9a-f]{64})$")


@dataclass(frozen=True)
class SnapshotBundle:
    snapshot_kind: str
    configuration_digest: str
    schema_versions: Mapping[str, JSONValue]
    frozen_review_set_digest: str
    material_input_digest: str
    source_revision_digest: str
    deterministic_pipeline_digest: str
    pipeline_fingerprint: Mapping[str, JSONValue]
    input_digest: str
    analysis_parent_snapshot_id: str | None
    parent_snapshot_id: str | None
    base_deterministic_snapshot_id: str | None
    records_by_type: Mapping[str, Sequence[Record]]
    report: str


@dataclass(frozen=True)
class PublishedSnapshot:
    snapshot_id: str
    snapshot_dir: Path
    observation_id: str
    reused: bool


@dataclass
class SnapshotWriter:
    project: ProjectPaths
    manifest_core: Mapping[str, JSONValue]
    records_by_type: dict[str, list[Record]] = field(
        default_factory=lambda: {record_type: [] for record_type in RECORD_TYPES}
    )

    @classmethod
    def create(
        cls, project: ProjectPaths, manifest_core: Mapping[str, JSONValue]
    ) -> "SnapshotWriter":
        required = {
            "snapshot_kind",
            "configuration_digest",
            "schema_versions",
            "frozen_review_set_digest",
            "material_input_digest",
            "source_revision_digest",
            "deterministic_pipeline_digest",
            "pipeline_fingerprint",
            "input_digest",
            "analysis_parent_snapshot_id",
            "parent_snapshot_id",
            "base_deterministic_snapshot_id",
        }
        missing = sorted(required - manifest_core.keys())
        if missing:
            raise ValueError(f"snapshot manifest core missing: {', '.join(missing)}")
        return cls(project, dict(manifest_core))

    def append(self, record_type: str, record: Record) -> None:
        if record_type not in RECORD_KIND_BY_TYPE:
            raise ValueError(f"unknown record type: {record_type}")
        self.records_by_type[record_type].append(record)

    def extend(self, record_type: str, records: Sequence[Record]) -> None:
        for record in records:
            self.append(record_type, record)

    def finalize(self, report: str) -> "SnapshotFinalizer":
        core = self.manifest_core
        bundle = SnapshotBundle(
            snapshot_kind=str(core["snapshot_kind"]),
            configuration_digest=str(core["configuration_digest"]),
            schema_versions=dict(core["schema_versions"]),
            frozen_review_set_digest=str(core["frozen_review_set_digest"]),
            material_input_digest=str(core["material_input_digest"]),
            source_revision_digest=str(core["source_revision_digest"]),
            deterministic_pipeline_digest=str(core["deterministic_pipeline_digest"]),
            pipeline_fingerprint=dict(core["pipeline_fingerprint"]),
            input_digest=str(core["input_digest"]),
            analysis_parent_snapshot_id=core["analysis_parent_snapshot_id"],
            parent_snapshot_id=core["parent_snapshot_id"],
            base_deterministic_snapshot_id=core["base_deterministic_snapshot_id"],
            records_by_type=self.records_by_type,
            report=report,
        )
        return SnapshotFinalizer(self.project, bundle)


@dataclass(frozen=True)
class SnapshotFinalizer:
    project: ProjectPaths
    bundle: SnapshotBundle

    def validate(self) -> None:
        if self.bundle.snapshot_kind != "deterministic":
            raise ValueError("Phase 1 publishes deterministic snapshots only")
        if (
            self.bundle.parent_snapshot_id is not None
            or self.bundle.base_deterministic_snapshot_id is not None
        ):
            raise ValueError(
                "Phase 1 deterministic snapshots cannot set layered parent fields"
            )
        if not isinstance(self.bundle.pipeline_fingerprint, Mapping) or (
            sha256_digest(canonical_bytes(self.bundle.pipeline_fingerprint))
            != self.bundle.deterministic_pipeline_digest
        ):
            raise ValueError(
                "pipeline fingerprint preimage does not match its digest"
            )
        normalized = {
            record_type: _deduplicate(
                record_type, list(self.bundle.records_by_type.get(record_type, ()))
            )
            for record_type in RECORD_TYPES
        }
        _validate_source_revision(self.bundle, normalized)
        _validate_references(normalized)

    def publish(
        self,
        observation: Mapping[str, JSONValue],
        expected_current_snapshot_id: str | None,
    ) -> PublishedSnapshot:
        self.validate()
        return publish_snapshot(
            self.project,
            self.bundle,
            observation,
            expected_current_snapshot_id,
        )


@dataclass(frozen=True)
class SnapshotReader:
    project: ProjectPaths
    snapshot_id: str
    snapshot_dir: Path
    manifest: Mapping[str, JSONValue]

    @classmethod
    def open(
        cls, project: ProjectPaths, snapshot_id: str | None = None
    ) -> "SnapshotReader":
        selected = snapshot_id
        if selected is None:
            if not project.current_path.is_file():
                raise FileNotFoundError("architecture graph current.json not found")
            current = json.loads(project.current_path.read_text(encoding="utf-8"))
            selected = current["snapshot_id"]
        if not isinstance(selected, str):
            raise ValueError("invalid snapshot ID")
        match = SNAPSHOT_ID.fullmatch(selected)
        if match is None:
            raise ValueError(f"invalid snapshot ID: {selected}")
        snapshot_dir = project.snapshots_dir / match.group(2)
        manifest_path = snapshot_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"snapshot not found: {selected}")
        manifest = _validate_snapshot_contents(snapshot_dir, selected)
        return cls(project, selected, snapshot_dir, manifest)

    def iter(self, record_type: str):
        if record_type not in RECORD_KIND_BY_TYPE:
            raise ValueError(f"unknown record type: {record_type}")
        return iter_records(
            self.snapshot_dir / f"{record_type}.jsonl",
            RECORD_KIND_BY_TYPE[record_type],
        )

    def get(self, record_type: str, record_id: str) -> Record | None:
        if record_type not in RECORD_KIND_BY_TYPE:
            raise ValueError(f"unknown record type: {record_type}")
        return get_record(self.snapshot_dir / f"{record_type}.jsonl", record_id)

    def select(
        self,
        record_type: str,
        filters: Mapping[str, JSONValue],
        fields: Sequence[str] | None,
        limit: int,
    ) -> list[Record]:
        if record_type not in RECORD_KIND_BY_TYPE:
            raise ValueError(f"unknown record type: {record_type}")
        return select_records(
            self.snapshot_dir / f"{record_type}.jsonl", filters, fields, limit
        )


def _file_digest(path: Path) -> str:
    return sha256_digest(path.read_bytes())


def _validate_snapshot_contents(
    snapshot_dir: Path, expected_snapshot_id: str
) -> Mapping[str, JSONValue]:
    manifest_path = snapshot_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"snapshot integrity error at {snapshot_dir}: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"snapshot integrity error at {snapshot_dir}: manifest is not an object")
    content_digest = manifest.get("content_digest")
    manifest_core = {
        key: value for key, value in manifest.items() if key != "content_digest"
    }
    computed = sha256_digest(canonical_bytes(manifest_core))
    snapshot_kind = manifest.get("snapshot_kind")
    if (
        content_digest != computed
        or expected_snapshot_id != f"{snapshot_kind}:{computed.removeprefix('sha256:')}"
    ):
        raise ValueError(f"snapshot integrity error at {snapshot_dir}: manifest identity mismatch")
    payload_files = manifest.get("payload_files")
    if not isinstance(payload_files, dict) or any(
        not isinstance(name, str)
        or not isinstance(digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        for name, digest in payload_files.items()
    ):
        raise ValueError(f"snapshot integrity error at {snapshot_dir}: invalid payload table")
    expected_names = {"manifest.json", *payload_files}
    entries = list(snapshot_dir.iterdir())
    if {path.name for path in entries} != expected_names or any(
        not path.is_file() for path in entries
    ):
        raise ValueError(f"snapshot integrity error at {snapshot_dir}: unexpected payload")
    for name, digest in payload_files.items():
        if _file_digest(snapshot_dir / name) != digest:
            raise ValueError(f"snapshot integrity error at {snapshot_dir}: digest mismatch for {name}")
    return manifest


def _current(project: ProjectPaths) -> Mapping[str, JSONValue] | None:
    if not project.current_path.is_file():
        return None
    return json.loads(project.current_path.read_text(encoding="utf-8"))


def _deduplicate(record_type: str, records: Sequence[Record]) -> list[Record]:
    by_id: dict[str, Record] = {}
    for record in records:
        validate_record(record, RECORD_KIND_BY_TYPE[record_type])
        validate_record_shape(record)
        record_id = str(record["id"])
        previous = by_id.get(record_id)
        if previous is not None and previous["content_digest"] != record["content_digest"]:
            raise ValueError(f"conflicting duplicate stable ID in {record_type}: {record_id}")
        by_id[record_id] = record
    return [by_id[record_id] for record_id in sorted(by_id)]


def _validate_source_revision(
    bundle: SnapshotBundle,
    records_by_type: Mapping[str, Sequence[Record]],
) -> None:
    expected = source_revision_digest(
        str(record["content_hash"])
        for record in records_by_type.get("sources", ())
    )
    if bundle.source_revision_digest != expected:
        raise ValueError(
            "source revision digest mismatch: "
            f"expected {expected}, got {bundle.source_revision_digest}"
        )


def _validate_references(records_by_type: Mapping[str, Sequence[Record]]) -> None:
    ids = {
        str(record["id"])
        for records in records_by_type.values()
        for record in records
    }
    checks = {
        "sources": ("warning_ids", "derivation_ids"),
        "segments": ("source_version_id", "evidence_ids", "derivation_ids"),
        "evidence": ("source_version_id", "segment_id", "derivation_ids"),
        "warnings": ("source_version_id", "derivation_ids"),
        "derivations": ("input_ids",),
    }
    for record_type, fields in checks.items():
        for record in records_by_type.get(record_type, ()):
            for field in fields:
                raw = record.get(field)
                values = raw if isinstance(raw, list) else [raw]
                for value in values:
                    if value is not None and str(value) not in ids:
                        raise ValueError(
                            f"broken reference {record['id']}.{field}: {value}"
                        )


def _sync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_stage(
    project: ProjectPaths, bundle: SnapshotBundle
) -> tuple[Path, dict[str, JSONValue]]:
    if bundle.snapshot_kind != "deterministic":
        raise ValueError(
            "Phase 1 publishes deterministic snapshots only; "
            "Phase 2 adds kind-specific enriched/reviewed validators"
        )
    if bundle.parent_snapshot_id is not None or bundle.base_deterministic_snapshot_id is not None:
        raise ValueError("Phase 1 deterministic snapshots cannot set layered parent fields")
    for field, digest in {
        "configuration_digest": bundle.configuration_digest,
        "frozen_review_set_digest": bundle.frozen_review_set_digest,
        "material_input_digest": bundle.material_input_digest,
        "source_revision_digest": bundle.source_revision_digest,
        "deterministic_pipeline_digest": bundle.deterministic_pipeline_digest,
        "input_digest": bundle.input_digest,
    }.items():
        if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
            raise ValueError(f"invalid snapshot {field}")
    for parent in (
        bundle.analysis_parent_snapshot_id,
        bundle.parent_snapshot_id,
        bundle.base_deterministic_snapshot_id,
    ):
        if parent is not None and SNAPSHOT_ID.fullmatch(parent) is None:
            raise ValueError(f"invalid parent snapshot ID: {parent}")
    if not isinstance(bundle.pipeline_fingerprint, Mapping):
        raise ValueError("pipeline fingerprint preimage must be an object")
    if (
        sha256_digest(canonical_bytes(bundle.pipeline_fingerprint))
        != bundle.deterministic_pipeline_digest
    ):
        raise ValueError("pipeline fingerprint preimage does not match its digest")
    if not isinstance(bundle.schema_versions, Mapping) or any(
        not isinstance(key, str) or type(value) is not int or value < 1
        for key, value in bundle.schema_versions.items()
    ):
        raise ValueError("schema_versions must be a positive integer map")
    unknown = sorted(set(bundle.records_by_type) - set(RECORD_TYPES))
    if unknown:
        raise ValueError(f"unknown snapshot record types: {', '.join(unknown)}")
    project.project_dir.mkdir(parents=True, exist_ok=True)
    staging_root = project.project_dir / ".staging"
    staging_root.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="snapshot-", dir=staging_root))
    try:
        normalized = {
            record_type: _deduplicate(
                record_type, list(bundle.records_by_type.get(record_type, ()))
            )
            for record_type in RECORD_TYPES
        }
        _validate_source_revision(bundle, normalized)
        _validate_references(normalized)
        for record_type, records in normalized.items():
            path = staging / f"{record_type}.jsonl"
            write_records(path, records)
            _sync(path)
        report = bundle.report if bundle.report.endswith("\n") else f"{bundle.report}\n"
        report_path = staging / "report.md"
        report_path.write_text(report, encoding="utf-8", newline="\n")
        _sync(report_path)
        payload_files = {
            path.name: _file_digest(path)
            for path in sorted(staging.iterdir())
            if path.name != "manifest.json"
        }
        manifest_core: dict[str, JSONValue] = {
            "schema_version": 1,
            "schema_versions": dict(bundle.schema_versions),
            "snapshot_kind": bundle.snapshot_kind,
            "configuration_digest": bundle.configuration_digest,
            "frozen_review_set_digest": bundle.frozen_review_set_digest,
            "material_input_digest": bundle.material_input_digest,
            "source_revision_digest": bundle.source_revision_digest,
            "deterministic_pipeline_digest": bundle.deterministic_pipeline_digest,
            "pipeline_fingerprint": dict(bundle.pipeline_fingerprint),
            "input_digest": bundle.input_digest,
            "analysis_parent_snapshot_id": bundle.analysis_parent_snapshot_id,
            "parent_snapshot_id": bundle.parent_snapshot_id,
            "base_deterministic_snapshot_id": bundle.base_deterministic_snapshot_id,
            "payload_files": payload_files,
        }
        content_digest = sha256_digest(canonical_bytes(manifest_core))
        manifest = {**manifest_core, "content_digest": content_digest}
        atomic_write_json(staging / "manifest.json", manifest)
        _sync(staging)
        return staging, manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _verify_collision(target: Path, manifest: Mapping[str, JSONValue]) -> None:
    existing_path = target / "manifest.json"
    if not existing_path.is_file():
        raise ValueError(f"snapshot digest collision at {target}")
    existing = json.loads(existing_path.read_text(encoding="utf-8"))
    if existing != manifest:
        raise ValueError(f"snapshot digest collision at {target}")
    expected_snapshot_id = (
        f"{manifest['snapshot_kind']}:"
        f"{str(manifest['content_digest']).removeprefix('sha256:')}"
    )
    try:
        _validate_snapshot_contents(target, expected_snapshot_id)
    except ValueError as error:
        raise ValueError(f"snapshot digest collision at {target}: {error}") from error


def publish_snapshot(
    project: ProjectPaths,
    bundle: SnapshotBundle,
    observation: Mapping[str, JSONValue],
    expected_current_snapshot_id: str | None,
) -> PublishedSnapshot:
    allowed_observation_keys = {"branch", "commit", "dirty_fingerprint", "observed_at"}
    unknown_observation_keys = sorted(set(observation) - allowed_observation_keys)
    if unknown_observation_keys:
        raise ValueError(
            f"unknown observation keys: {', '.join(unknown_observation_keys)}"
        )
    missing_observation_keys = sorted(allowed_observation_keys - observation.keys())
    if missing_observation_keys:
        raise ValueError(
            f"missing observation keys: {', '.join(missing_observation_keys)}"
        )
    staging, manifest = _write_stage(project, bundle)
    content_digest = str(manifest["content_digest"])
    digest_hex = content_digest.removeprefix("sha256:")
    snapshot_id = f"{bundle.snapshot_kind}:{digest_hex}"
    target = project.snapshots_dir / digest_hex
    reused = False
    observation_record = finalize_record(
        {
            "id": stable_id(
                "observation",
                snapshot_id,
                observation.get("observed_at"),
                observation.get("commit"),
                observation.get("dirty_fingerprint"),
            ),
            "kind": "observation",
            "snapshot_id": snapshot_id,
            "previous_current_snapshot_id": expected_current_snapshot_id,
            "base_deterministic_snapshot_id": (
                bundle.base_deterministic_snapshot_id or snapshot_id
            ),
            "material_input_digest": bundle.material_input_digest,
            "source_revision_digest": bundle.source_revision_digest,
            **dict(observation),
        }
    )
    validate_record_shape(observation_record)
    try:
        with ProjectLock(project.lock_path):
            current = _current(project)
            actual_current = None if current is None else str(current["snapshot_id"])
            if actual_current != expected_current_snapshot_id:
                raise RuntimeError(
                    f"current snapshot changed: expected {expected_current_snapshot_id}, got {actual_current}"
                )
            project.snapshots_dir.mkdir(parents=True, exist_ok=True)
            if target.exists():
                _verify_collision(target, manifest)
                reused = True
            else:
                os.replace(staging, target)
                _sync(project.snapshots_dir)
            atomic_write_json(
                project.project_file,
                {
                    "schema_version": 1,
                    "project_id": project.project_id,
                    "repository_root": project.root.as_posix(),
                },
            )
            AtomicJsonlLedger(project.observations_path).append(observation_record)
            atomic_write_json(
                project.current_path,
                {
                    "schema_version": 1,
                    "snapshot_id": snapshot_id,
                    "observation_id": observation_record["id"],
                    "published_at": observation.get("observed_at"),
                },
            )
            return PublishedSnapshot(
                snapshot_id=snapshot_id,
                snapshot_dir=target,
                observation_id=str(observation_record["id"]),
                reused=reused,
            )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def observe_existing_snapshot(
    project: ProjectPaths,
    reader: SnapshotReader,
    observation: Mapping[str, JSONValue],
    expected_current_snapshot_id: str,
) -> PublishedSnapshot:
    allowed = {"branch", "commit", "dirty_fingerprint", "observed_at"}
    if set(observation) != allowed:
        raise ValueError("existing-snapshot observation fields are invalid")
    with ProjectLock(project.lock_path):
        current = _current(project)
        actual = None if current is None else str(current["snapshot_id"])
        if actual != expected_current_snapshot_id or actual != reader.snapshot_id:
            raise RuntimeError(
                f"current snapshot changed: expected {expected_current_snapshot_id}, got {actual}"
            )
        record = finalize_record(
            {
                "id": stable_id(
                    "observation",
                    reader.snapshot_id,
                    observation["observed_at"],
                    observation["commit"],
                    observation["dirty_fingerprint"],
                ),
                "kind": "observation",
                "snapshot_id": reader.snapshot_id,
                "previous_current_snapshot_id": actual,
                "base_deterministic_snapshot_id": reader.manifest.get(
                    "base_deterministic_snapshot_id"
                )
                or reader.snapshot_id,
                "material_input_digest": reader.manifest["material_input_digest"],
                "source_revision_digest": reader.manifest["source_revision_digest"],
                **dict(observation),
            }
        )
        validate_record_shape(record)
        AtomicJsonlLedger(project.observations_path).append(record)
        atomic_write_json(
            project.current_path,
            {
                "schema_version": 1,
                "snapshot_id": reader.snapshot_id,
                "observation_id": record["id"],
                "published_at": observation["observed_at"],
            },
        )
        return PublishedSnapshot(
            snapshot_id=reader.snapshot_id,
            snapshot_dir=reader.snapshot_dir,
            observation_id=str(record["id"]),
            reused=True,
        )
