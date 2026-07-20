from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unicodedata

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
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED_SCHEMA_VERSIONS = {"snapshot": 1, "records": 1}
EXPECTED_PAYLOAD_FILES = frozenset(
    {f"{record_type}.jsonl" for record_type in RECORD_TYPES} | {"report.md"}
)
MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "schema_versions",
        "snapshot_kind",
        "configuration_digest",
        "frozen_review_set_digest",
        "material_input_digest",
        "source_revision_digest",
        "deterministic_pipeline_digest",
        "pipeline_fingerprint",
        "input_digest",
        "analysis_parent_snapshot_id",
        "parent_snapshot_id",
        "base_deterministic_snapshot_id",
        "payload_files",
        "content_digest",
    }
)


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
        _normalize_and_validate_bundle(self.bundle)

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
        if not snapshot_dir.exists():
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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _validate_snapshot_contents(
    snapshot_dir: Path, expected_snapshot_id: str
) -> Mapping[str, JSONValue]:
    try:
        return _validate_snapshot_contents_inner(snapshot_dir, expected_snapshot_id)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(
            f"snapshot integrity error at {snapshot_dir}: {error}"
        ) from error


def _validate_snapshot_contents_inner(
    snapshot_dir: Path, expected_snapshot_id: str
) -> Mapping[str, JSONValue]:
    id_match = SNAPSHOT_ID.fullmatch(expected_snapshot_id)
    if id_match is None or snapshot_dir.name != id_match.group(2):
        raise ValueError("snapshot ID/path identity mismatch")
    if snapshot_dir.is_symlink() or not stat.S_ISDIR(
        snapshot_dir.stat(follow_symlinks=False).st_mode
    ):
        raise ValueError("snapshot path is not a regular directory")

    manifest_path = snapshot_dir / "manifest.json"
    if manifest_path.is_symlink() or not stat.S_ISREG(
        manifest_path.stat(follow_symlinks=False).st_mode
    ):
        raise ValueError("manifest is not a regular file")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest is not an object")
    if manifest_bytes != canonical_bytes(manifest):
        raise ValueError("manifest bytes are not canonical")
    if set(manifest) != MANIFEST_KEYS:
        raise ValueError("manifest fields do not match the snapshot schema")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported manifest schema_version")

    content_digest = manifest["content_digest"]
    if not isinstance(content_digest, str) or DIGEST.fullmatch(content_digest) is None:
        raise ValueError("invalid snapshot content_digest")
    manifest_core = {
        key: value for key, value in manifest.items() if key != "content_digest"
    }
    computed = sha256_digest(canonical_bytes(manifest_core))
    snapshot_kind = manifest["snapshot_kind"]
    computed_id = f"{snapshot_kind}:{computed.removeprefix('sha256:')}"
    if content_digest != computed or expected_snapshot_id != computed_id:
        raise ValueError("manifest identity mismatch")
    if snapshot_kind != id_match.group(1):
        raise ValueError("snapshot kind does not match its ID")

    _validate_snapshot_metadata(
        snapshot_kind=snapshot_kind,
        configuration_digest=manifest["configuration_digest"],
        schema_versions=manifest["schema_versions"],
        frozen_review_set_digest=manifest["frozen_review_set_digest"],
        material_input_digest=manifest["material_input_digest"],
        source_revision=manifest["source_revision_digest"],
        deterministic_pipeline_digest=manifest["deterministic_pipeline_digest"],
        pipeline_fingerprint=manifest["pipeline_fingerprint"],
        input_digest=manifest["input_digest"],
        analysis_parent_snapshot_id=manifest["analysis_parent_snapshot_id"],
        parent_snapshot_id=manifest["parent_snapshot_id"],
        base_deterministic_snapshot_id=manifest["base_deterministic_snapshot_id"],
    )

    payload_files = manifest["payload_files"]
    if not isinstance(payload_files, dict) or set(payload_files) != EXPECTED_PAYLOAD_FILES:
        raise ValueError("payload table does not contain the required payload family")
    if any(
        not isinstance(digest, str) or DIGEST.fullmatch(digest) is None
        for digest in payload_files.values()
    ):
        raise ValueError("invalid payload table digest")

    entries = list(snapshot_dir.iterdir())
    if {path.name for path in entries} != {"manifest.json", *EXPECTED_PAYLOAD_FILES}:
        raise ValueError("unexpected snapshot payload")
    if any(
        path.is_symlink()
        or not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
        for path in entries
    ):
        raise ValueError("snapshot contains a non-regular payload")
    for name, digest in payload_files.items():
        if _file_digest(snapshot_dir / name) != digest:
            raise ValueError(f"digest mismatch for {name}")

    records_by_type = {
        record_type: _read_canonical_records(
            snapshot_dir / f"{record_type}.jsonl", record_type
        )
        for record_type in RECORD_TYPES
    }
    report_path = snapshot_dir / "report.md"
    report_bytes = report_path.read_bytes()
    report = report_bytes.decode("utf-8")
    if report_bytes != _canonical_report(report).encode("utf-8"):
        raise ValueError("report.md bytes are not canonical")
    _validate_source_revision(str(manifest["source_revision_digest"]), records_by_type)
    _validate_references(records_by_type)
    return manifest


def _current(project: ProjectPaths) -> Mapping[str, JSONValue] | None:
    if not project.current_path.is_file():
        return None
    return json.loads(project.current_path.read_text(encoding="utf-8"))


def _deduplicate(record_type: str, records: Sequence[Record]) -> list[Record]:
    by_id: dict[str, Record] = {}
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError(f"record in {record_type} is not an object")
        record = json.loads(canonical_bytes(raw_record))
        if not isinstance(record, dict):
            raise ValueError(f"record in {record_type} is not an object")
        validate_record(record, RECORD_KIND_BY_TYPE[record_type])
        validate_record_shape(record)
        record_id = str(record["id"])
        _validate_record_id(record_type, record_id)
        previous = by_id.get(record_id)
        if previous is not None and previous["content_digest"] != record["content_digest"]:
            raise ValueError(f"conflicting duplicate stable ID in {record_type}: {record_id}")
        by_id[record_id] = record
    return [by_id[record_id] for record_id in sorted(by_id)]


def _validate_source_revision(
    actual: str,
    records_by_type: Mapping[str, Sequence[Record]],
) -> None:
    expected = source_revision_digest(
        str(record["content_hash"])
        for record in records_by_type.get("sources", ())
    )
    if actual != expected:
        raise ValueError(
            "source revision digest mismatch: "
            f"expected {expected}, got {actual}"
        )


def _validate_record_id(record_type: str, record_id: str) -> None:
    prefix = f"{RECORD_KIND_BY_TYPE[record_type]}:"
    if not record_id.startswith(prefix) or record_id == prefix:
        raise ValueError(
            f"{RECORD_KIND_BY_TYPE[record_type]} ID must start with {prefix}"
        )


def _read_canonical_records(path: Path, record_type: str) -> list[Record]:
    records: list[Record] = []
    previous_id: str | None = None
    with path.open("rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise ValueError(f"{path.name} has non-LF framing")
            record = json.loads(line.decode("utf-8"))
            if not isinstance(record, dict):
                raise ValueError(f"JSONL record is not an object: {path}")
            if line != canonical_bytes(record):
                raise ValueError(f"{path.name} contains noncanonical JSON")
            validate_record(record, RECORD_KIND_BY_TYPE[record_type])
            validate_record_shape(record)
            record_id = str(record["id"])
            _validate_record_id(record_type, record_id)
            if previous_id is not None and record_id <= previous_id:
                raise ValueError(f"{path.name} records are not strictly ID sorted")
            previous_id = record_id
            records.append(record)
    return records


def _validate_digest(field: str, value: object) -> None:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid snapshot {field}")


def _validate_schema_versions(value: object) -> None:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or type(version) is not int or version < 1
        for key, version in value.items()
    ):
        raise ValueError("schema_versions must be a positive integer map")
    if dict(value) != EXPECTED_SCHEMA_VERSIONS:
        raise ValueError(
            "schema_versions must identify snapshot and records schema version 1"
        )


def _validate_snapshot_metadata(
    *,
    snapshot_kind: object,
    configuration_digest: object,
    schema_versions: object,
    frozen_review_set_digest: object,
    material_input_digest: object,
    source_revision: object,
    deterministic_pipeline_digest: object,
    pipeline_fingerprint: object,
    input_digest: object,
    analysis_parent_snapshot_id: object,
    parent_snapshot_id: object,
    base_deterministic_snapshot_id: object,
) -> None:
    if snapshot_kind != "deterministic":
        raise ValueError("Phase 1 publishes deterministic snapshots only")
    for field, digest in {
        "configuration_digest": configuration_digest,
        "frozen_review_set_digest": frozen_review_set_digest,
        "material_input_digest": material_input_digest,
        "source_revision_digest": source_revision,
        "deterministic_pipeline_digest": deterministic_pipeline_digest,
        "input_digest": input_digest,
    }.items():
        _validate_digest(field, digest)
    _validate_schema_versions(schema_versions)

    if analysis_parent_snapshot_id is not None:
        if (
            not isinstance(analysis_parent_snapshot_id, str)
            or SNAPSHOT_ID.fullmatch(analysis_parent_snapshot_id) is None
            or not analysis_parent_snapshot_id.startswith("deterministic:")
        ):
            raise ValueError("invalid analysis parent snapshot ID")
    for field, parent in {
        "parent": parent_snapshot_id,
        "base deterministic": base_deterministic_snapshot_id,
    }.items():
        if parent is not None and (
            not isinstance(parent, str) or SNAPSHOT_ID.fullmatch(parent) is None
        ):
            raise ValueError(f"invalid {field} snapshot ID")
    if parent_snapshot_id is not None or base_deterministic_snapshot_id is not None:
        raise ValueError(
            "Phase 1 deterministic snapshots cannot set layered parent fields"
        )
    if not isinstance(pipeline_fingerprint, Mapping):
        raise ValueError("pipeline fingerprint preimage must be an object")
    try:
        fingerprint_digest = sha256_digest(canonical_bytes(pipeline_fingerprint))
    except (TypeError, ValueError) as error:
        raise ValueError("pipeline fingerprint preimage is not canonical JSON") from error
    if fingerprint_digest != deterministic_pipeline_digest:
        raise ValueError("pipeline fingerprint preimage does not match its digest")


def _normalize_and_validate_bundle(
    bundle: SnapshotBundle,
) -> dict[str, list[Record]]:
    _validate_snapshot_metadata(
        snapshot_kind=bundle.snapshot_kind,
        configuration_digest=bundle.configuration_digest,
        schema_versions=bundle.schema_versions,
        frozen_review_set_digest=bundle.frozen_review_set_digest,
        material_input_digest=bundle.material_input_digest,
        source_revision=bundle.source_revision_digest,
        deterministic_pipeline_digest=bundle.deterministic_pipeline_digest,
        pipeline_fingerprint=bundle.pipeline_fingerprint,
        input_digest=bundle.input_digest,
        analysis_parent_snapshot_id=bundle.analysis_parent_snapshot_id,
        parent_snapshot_id=bundle.parent_snapshot_id,
        base_deterministic_snapshot_id=bundle.base_deterministic_snapshot_id,
    )
    if not isinstance(bundle.records_by_type, Mapping) or any(
        not isinstance(record_type, str) for record_type in bundle.records_by_type
    ):
        raise ValueError("snapshot records_by_type must be an object")
    unknown = sorted(set(bundle.records_by_type) - set(RECORD_TYPES))
    if unknown:
        raise ValueError(f"unknown snapshot record types: {', '.join(unknown)}")
    normalized: dict[str, list[Record]] = {}
    for record_type in RECORD_TYPES:
        raw_records = bundle.records_by_type.get(record_type, ())
        if isinstance(raw_records, (str, bytes)) or not isinstance(
            raw_records, Sequence
        ):
            raise ValueError(f"snapshot {record_type} payload must be a sequence")
        normalized[record_type] = _deduplicate(record_type, raw_records)
    _validate_source_revision(bundle.source_revision_digest, normalized)
    _validate_references(normalized)
    _canonical_report(bundle.report)
    return normalized


def _canonical_report(report: str) -> str:
    if not isinstance(report, str):
        raise ValueError("snapshot report must be a string")
    normalized = unicodedata.normalize(
        "NFC", report.replace("\r\n", "\n").replace("\r", "\n")
    )
    return normalized.rstrip("\n") + "\n"


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
    normalized = _normalize_and_validate_bundle(bundle)
    project.project_dir.mkdir(parents=True, exist_ok=True)
    staging_root = project.project_dir / ".staging"
    staging_root.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="snapshot-", dir=staging_root))
    try:
        for record_type, records in normalized.items():
            path = staging / f"{record_type}.jsonl"
            write_records(path, records)
            _sync(path)
        report_path = staging / "report.md"
        report_path.write_bytes(_canonical_report(bundle.report).encode("utf-8"))
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
    expected_snapshot_id = (
        f"{manifest['snapshot_kind']}:"
        f"{str(manifest['content_digest']).removeprefix('sha256:')}"
    )
    try:
        existing = _validate_snapshot_contents(target, expected_snapshot_id)
    except ValueError as error:
        raise ValueError(f"snapshot digest collision at {target}: {error}") from error
    if existing != manifest:
        raise ValueError(f"snapshot digest collision at {target}")


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
                    "current snapshot changed: "
                    f"expected {expected_current_snapshot_id}, got {actual_current}"
                )
            project.snapshots_dir.mkdir(parents=True, exist_ok=True)
            if target.exists():
                _verify_collision(target, manifest)
                reused = True
            else:
                staging_parent = staging.parent
                os.replace(staging, target)
                _sync(staging_parent)
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
        match = SNAPSHOT_ID.fullmatch(reader.snapshot_id)
        expected_dir = (
            None if match is None else project.snapshots_dir / match.group(2)
        )
        if reader.project != project or reader.snapshot_dir != expected_dir:
            raise ValueError("snapshot reader does not belong to this project")
        fresh_manifest = _validate_snapshot_contents(
            reader.snapshot_dir, reader.snapshot_id
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
                "base_deterministic_snapshot_id": fresh_manifest.get(
                    "base_deterministic_snapshot_id"
                )
                or reader.snapshot_id,
                "material_input_digest": fresh_manifest["material_input_digest"],
                "source_revision_digest": fresh_manifest["source_revision_digest"],
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
