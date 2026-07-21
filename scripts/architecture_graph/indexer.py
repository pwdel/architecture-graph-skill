from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import subprocess

from architecture_graph import __version__
from architecture_graph.analysis import analyze_catalog
from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.canonical import (
    canonical_bytes,
    sha256_digest,
    source_revision_digest,
    stable_id,
)
from architecture_graph.config import (
    ConfigurationPathError,
    ProjectConfig,
    configuration_identity,
    configuration_digest,
    load_config,
    resolve_config_path,
)
from architecture_graph.corpus import (
    CorpusSelection,
    check_default_memory_ignored,
    check_memory_ignored,
    resolve_corpus,
    write_corpus_metadata,
)
from architecture_graph.fingerprint import pipeline_fingerprint
from architecture_graph.ingest import IngestionContext, IngestionResult, ingest_sources
from architecture_graph.ingest.diagrams import warning_record
from architecture_graph.jsonl_store import get_record
from architecture_graph.project import (
    ProjectPaths,
    RepositoryStateError,
    _decode_git_path,
    capture_git_observation,
)
from architecture_graph.records import (
    RECORD_KIND_BY_TYPE,
    Record,
    finalize_record,
    validate_record,
    validate_record_shape,
)
from architecture_graph.snapshot import (
    SnapshotBundle,
    SnapshotReader,
    _validated_observation,
    observe_existing_snapshot,
    publish_snapshot,
)
from architecture_graph.sources import (
    SourceInput,
    discover_sources,
    material_input_digest,
    source_record_base,
    source_record_id,
)


@dataclass(frozen=True)
class IndexResult:
    snapshot_id: str
    observation_id: str
    reused: bool
    source_count: int
    segment_count: int
    warning_count: int
    selection: CorpusSelection | None = None

    @property
    def corpus_id(self) -> str | None:
        return None if self.selection is None else self.selection.corpus_id

    def as_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("selection", None)
        if self.corpus_id is not None:
            payload["corpus_id"] = self.corpus_id
        return payload


def _source_metadata(ingestion: IngestionResult) -> dict[str, dict[str, object]]:
    metadata_by_source: dict[str, dict[str, object]] = {}
    for segment in ingestion.segments:
        source_id = str(segment["source_version_id"])
        metadata = segment["metadata"]
        if not isinstance(metadata, dict):
            continue
        if segment["segment_kind"] == "metadata_field":
            key = metadata.get("metadata_key")
            if isinstance(key, str):
                metadata_by_source.setdefault(source_id, {})[key] = metadata.get(
                    "metadata_value"
                )
        elif (
            segment["segment_kind"] == "structured_scalar"
            and metadata.get("json_pointer") == "/id"
            and isinstance(metadata.get("scalar_value"), str)
        ):
            metadata_by_source.setdefault(source_id, {})["id"] = metadata[
                "scalar_value"
            ]
    return metadata_by_source


@dataclass(frozen=True)
class RenameResolution:
    pairs: dict[str, str]
    ambiguous_targets: dict[str, tuple[str, ...]]
    unresolved_targets: dict[str, tuple[str, ...]]

    def as_digest_input(self) -> dict[str, object]:
        return {
            "pairs": [[new, old] for new, old in sorted(self.pairs.items())],
            "ambiguous_targets": [
                [target, list(origins)]
                for target, origins in sorted(self.ambiguous_targets.items())
            ],
            "unresolved_targets": [
                [new, list(old_paths)]
                for new, old_paths in sorted(self.unresolved_targets.items())
            ],
        }

    def relevant_to(
        self, new_paths: set[str], prior_paths: set[str]
    ) -> "RenameResolution":
        return RenameResolution(
            {
                new: old
                for new, old in self.pairs.items()
                if new in new_paths and old in prior_paths
            },
            {
                target: tuple(origin for origin in origins if origin in prior_paths)
                for target, origins in self.ambiguous_targets.items()
                if target in new_paths
                and len([origin for origin in origins if origin in prior_paths]) > 0
            },
            {
                new: tuple(old for old in old_paths if old in prior_paths)
                for new, old_paths in self.unresolved_targets.items()
                if new in new_paths
                and len([old for old in old_paths if old in prior_paths]) > 0
            },
        )


def _git_rename_resolution(
    root: Path,
    previous_commit: str | None,
    current_content_hashes: Mapping[str, str],
    prior_content_hashes: Mapping[str, str],
) -> RenameResolution:
    new_paths = set(current_content_hashes)
    prior_paths = set(prior_content_hashes)
    deleted = prior_paths - new_paths
    added = new_paths - prior_paths

    def git_bytes(*args: str) -> bytes:
        try:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            operation = args[0] if args else "command"
            raise RepositoryStateError(
                f"Git {operation} failed while resolving source lineage"
            ) from error

    if previous_commit is not None:
        fields = git_bytes(
            "diff",
            "--name-status",
            "-z",
            "--no-renames",
            previous_commit,
            "--",
        ).split(b"\0")
        cursor = 0
        while cursor < len(fields) and fields[cursor]:
            if cursor + 1 >= len(fields):
                raise RepositoryStateError("Git returned malformed name status")
            status = _decode_git_path(fields[cursor])
            path = _decode_git_path(fields[cursor + 1])
            cursor += 2
            if status not in {"A", "D", "M", "T", "U", "X", "B"}:
                raise RepositoryStateError("Git returned invalid name status")
            if status == "D" and path in prior_paths:
                deleted.add(path)
            elif status == "A" and path in new_paths:
                added.add(path)
        untracked = git_bytes(
            "ls-files", "--others", "--exclude-standard", "-z"
        ).split(b"\0")
        added.update(
            path
            for path in (_decode_git_path(item) for item in untracked if item)
            if path in new_paths
        )

    changed_same_paths = {
        path
        for path in new_paths.intersection(prior_paths)
        if current_content_hashes[path] != prior_content_hashes[path]
    }
    candidate_targets = added | changed_same_paths
    candidate_origins = deleted | changed_same_paths
    direct_origins: dict[str, tuple[str, ...]] = {}
    for target in sorted(candidate_targets):
        origins: set[str] = set()
        if target in changed_same_paths:
            origins.add(target)
        origins.update(
            origin
            for origin in candidate_origins
            if origin != target
            and prior_content_hashes[origin] == current_content_hashes[target]
        )
        if origins:
            direct_origins[target] = tuple(sorted(origins))

    origin_degree = {
        origin: sum(origin in origins for origins in direct_origins.values())
        for origin in sorted(candidate_origins)
    }
    pairs: dict[str, str] = {}
    ambiguous: dict[str, tuple[str, ...]] = {}
    for target, origins in sorted(direct_origins.items()):
        isolated = len(origins) == 1 and origin_degree[origins[0]] == 1
        if isolated and target == origins[0]:
            continue
        if isolated:
            pairs[target] = origins[0]
        else:
            ambiguous[target] = origins
    unresolved = {
        new: tuple(sorted(deleted))
        for new in sorted(added)
        if deleted
        and new not in direct_origins
        and new not in pairs
        and new not in ambiguous
    }
    return RenameResolution(
        dict(sorted(pairs.items())),
        dict(sorted(ambiguous.items())),
        unresolved,
    )


def _selected_observation_commit(
    project: ProjectPaths,
    current: SnapshotReader | None,
    analysis_parent_snapshot_id: str | None,
) -> str | None:
    if current is None:
        return None
    try:
        pointer = json.loads(project.current_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("current pointer is unreadable") from error
    if not isinstance(pointer, dict) or set(pointer) != {
        "schema_version",
        "snapshot_id",
        "observation_id",
        "published_at",
    }:
        raise ValueError("current pointer has invalid shape")
    if pointer["schema_version"] != 1 or pointer["snapshot_id"] != current.snapshot_id:
        raise ValueError("current pointer does not match selected snapshot")
    observation_id = pointer["observation_id"]
    if not isinstance(observation_id, str):
        raise ValueError("current pointer has invalid observation ID")
    observation = get_record(project.observations_path, observation_id)
    if observation is None:
        raise ValueError("selected observation is missing")
    validate_record(observation, "observation")
    validate_record_shape(observation)
    validated_observation = _validated_observation(
        {
            "branch": observation["branch"],
            "commit": observation["commit"],
            "dirty_fingerprint": observation["dirty_fingerprint"],
            "observed_at": observation["observed_at"],
        }
    )
    if observation["snapshot_id"] != current.snapshot_id:
        raise ValueError("selected observation names a different snapshot")
    if observation["base_deterministic_snapshot_id"] != analysis_parent_snapshot_id:
        raise ValueError("selected observation names a different analysis parent")
    if observation["material_input_digest"] != current.manifest[
        "material_input_digest"
    ]:
        raise ValueError("selected observation material digest mismatch")
    if observation["source_revision_digest"] != current.manifest[
        "source_revision_digest"
    ]:
        raise ValueError("selected observation source revision mismatch")
    if (
        not isinstance(pointer["published_at"], str)
        or pointer["published_at"] != observation["observed_at"]
    ):
        raise ValueError("current pointer timestamp does not match selected observation")
    validated_commit = validated_observation["commit"]
    return None if validated_commit is None else str(validated_commit)


def _logical_source_ids(
    project: ProjectPaths,
    analysis_parent: SnapshotReader | None,
    inputs: Sequence[SourceInput],
    ingestion: IngestionResult,
    rename_resolution: RenameResolution,
) -> dict[str, str]:
    prior_paths = (
        {}
        if analysis_parent is None
        else {
            str(source["path"]): str(source["logical_source_id"])
            for source in analysis_parent.iter("sources")
        }
    )
    renames = rename_resolution.pairs
    ambiguous_targets = set(rename_resolution.ambiguous_targets)
    metadata_by_source = _source_metadata(ingestion)
    explicit_content_hashes: dict[str, str] = {}
    resolved: dict[str, str] = {}
    for source in sorted(inputs, key=lambda item: item.relative_path):
        source_id = source_record_id(source)
        raw_explicit = metadata_by_source.get(source_id, {}).get("id")
        explicit = (
            raw_explicit.strip().casefold()
            if isinstance(raw_explicit, str) and raw_explicit.strip()
            else None
        )
        if explicit is not None:
            previous_content_hash = explicit_content_hashes.get(explicit)
            if (
                previous_content_hash is not None
                and previous_content_hash != source.content_hash
            ):
                raise ValueError(
                    "duplicate explicit document ID with different content: "
                    f"{raw_explicit}"
                )
            explicit_content_hashes[explicit] = source.content_hash
            logical_id = stable_id("logical-source", "explicit", explicit)
        elif source.relative_path in ambiguous_targets:
            logical_id = stable_id(
                "logical-source",
                project.project_id,
                analysis_parent.snapshot_id if analysis_parent is not None else "genesis",
                "ambiguous-add-remove",
                source.relative_path,
                source.content_hash,
            )
        elif source.relative_path in prior_paths:
            logical_id = str(prior_paths[source.relative_path])
        elif source.relative_path in renames and renames[source.relative_path] in prior_paths:
            logical_id = str(prior_paths[renames[source.relative_path]])
        else:
            logical_id = stable_id(
                "logical-source",
                project.project_id,
                "genesis" if analysis_parent is None else analysis_parent.snapshot_id,
                source.relative_path,
                source.content_hash,
            )
        resolved[source_id] = logical_id
    return resolved


def _rename_resolution_warnings(
    inputs: Sequence[SourceInput],
    resolution: RenameResolution,
    context: IngestionContext,
) -> IngestionResult:
    by_path = {item.relative_path: item for item in inputs}
    derivations: list[Record] = []
    warnings: list[Record] = []
    cases = [
        ("ambiguous_rename", target, candidates)
        for target, candidates in sorted(resolution.ambiguous_targets.items())
    ]
    cases.extend(
        ("unresolved_rename", target, candidates)
        for target, candidates in sorted(resolution.unresolved_targets.items())
    )
    for code, target, candidates in cases:
        source = by_path.get(target)
        if source is None:
            continue
        source_id = source_record_id(source)
        resolution_key = stable_id("rename-resolution", code, target, list(candidates))
        derivation = finalize_record(
            {
                "id": stable_id(
                    "derivation",
                    "deterministic",
                    "git_rename_resolution",
                    context.tool_version,
                    context.configuration_digest,
                    context.pipeline_digest,
                    source_id,
                    "warning",
                    resolution_key,
                ),
                "kind": "derivation",
                "producer_kind": "deterministic",
                "method": "git_rename_resolution",
                "tool": "architecture-graph",
                "tool_version": context.tool_version,
                "model": None,
                "model_version": None,
                "model_artifact_digest": None,
                "configuration_digest": context.configuration_digest,
                "pipeline_digest": context.pipeline_digest,
                "input_ids": [source_id],
                "output_kind": "warning",
                "output_identity_key": resolution_key,
                "created_at": None,
            }
        )
        derivations.append(derivation)
        warnings.append(
            warning_record(
                source,
                code=code,
                message=(
                    (
                        f"Source lineage target {target} has a competing "
                        "exact-digest/path-continuity origin assignment involving: "
                    )
                    if code == "ambiguous_rename"
                    else (
                        f"Git rename target {target} has no exact parent digest match; "
                        "the parent snapshot has no persisted raw bytes for a "
                        "trustworthy similarity comparison among: "
                    )
                )
                + ", ".join(candidates)
                + "; treating it as an add/remove",
                span=None,
                possible_role=source.document_role,
                derivation_ids=(str(derivation["id"]),),
            )
        )
    return IngestionResult(derivations=tuple(derivations), warnings=tuple(warnings))


def _source_records(
    inputs: Sequence[SourceInput],
    ingestion: IngestionResult,
    context: IngestionContext,
    logical_source_ids: Mapping[str, str],
) -> tuple[list[Record], list[Record]]:
    warnings_by_source: dict[str, list[str]] = {}
    metadata_by_source = _source_metadata(ingestion)
    for warning in ingestion.warnings:
        source_id = str(warning["source_version_id"])
        warnings_by_source.setdefault(source_id, []).append(str(warning["id"]))
    enriched: list[Record] = []
    source_derivations: list[Record] = []
    derivations_by_source: dict[str, set[str]] = {}
    source_ids = {source_record_id(item) for item in inputs}
    for derivation in ingestion.derivations:
        for input_id in derivation["input_ids"]:
            if str(input_id) in source_ids:
                derivations_by_source.setdefault(str(input_id), set()).add(
                    str(derivation["id"])
                )
    for source in inputs:
        source_id = source_record_id(source)
        raw = source_record_base(source, logical_source_ids[source_id])
        warning_ids = sorted(warnings_by_source.get(source_id, ()))
        warning_codes = {
            str(item["code"])
            for item in ingestion.warnings
            if item["source_version_id"] == source_id
        }
        adapter_warning_codes = warning_codes - {
            "ambiguous_rename",
            "unresolved_rename",
        }
        source_has_segments = any(
            item["source_version_id"] == source_id for item in ingestion.segments
        )
        parse_status = (
            "failed"
            if "parse_failed" in adapter_warning_codes and not source_has_segments
            else "partial"
            if adapter_warning_codes
            else "complete"
        )
        status = str(metadata_by_source.get(source_id, {}).get("status", "")).casefold()
        authority_class = source.authority_class
        authority_basis = source.authority_basis
        if source.authority_basis != "configured" and source.document_role == "adr":
            if status == "accepted":
                authority_class = "accepted_adr_or_active_standard"
                authority_basis = "adr_status"
            elif status in {"proposed", "draft"}:
                authority_class = "proposal_or_draft"
                authority_basis = "adr_status"
        direct_input_ids = sorted(derivations_by_source.get(source_id, ()))
        if not direct_input_ids:
            raise ValueError(f"source has no adapter derivation: {source.relative_path}")
        source_derivation = finalize_record(
            {
                "id": stable_id(
                    "derivation",
                    "deterministic",
                    "source_manifest",
                    context.tool_version,
                    context.configuration_digest,
                    context.pipeline_digest,
                    direct_input_ids,
                    "source",
                    source_id,
                ),
                "kind": "derivation",
                "producer_kind": "deterministic",
                "method": "source_manifest",
                "tool": "architecture-graph",
                "tool_version": context.tool_version,
                "model": None,
                "model_version": None,
                "model_artifact_digest": None,
                "configuration_digest": context.configuration_digest,
                "pipeline_digest": context.pipeline_digest,
                "input_ids": direct_input_ids,
                "output_kind": "source",
                "output_identity_key": source_id,
                "created_at": None,
            }
        )
        source_derivations.append(source_derivation)
        content = dict(raw)
        content.update(
            {
                "authority_class": authority_class,
                "authority_basis": authority_basis,
                "adr_metadata": metadata_by_source.get(source_id, {}),
                "adapter_name": source.source_kind,
                "adapter_version": "v1",
                "parse_status": parse_status,
                "warning_ids": warning_ids,
                "configuration_digest": context.configuration_digest,
                "deterministic_pipeline_digest": context.pipeline_digest,
                "derivation_ids": [source_derivation["id"]],
            }
        )
        enriched.append(finalize_record(content))
    return enriched, source_derivations


def _report(sources: Sequence[Record], ingestion: IngestionResult) -> str:
    source_paths = {str(item["id"]): str(item["path"]) for item in sources}
    lines = [
        "# Architecture Graph Ingestion",
        "",
        f"- Sources: {len(sources)}",
        f"- Segments: {len(ingestion.segments)}",
        f"- Warnings: {len(ingestion.warnings)}",
        "",
        "## Sources",
        "",
    ]
    lines.extend(
        f"- `{source['path']}`: {source['parse_status']} ({source['source_kind']})"
        for source in sorted(sources, key=lambda item: str(item["path"]))
    )
    lines.extend(["", "## Warnings", ""])
    if ingestion.warnings:
        for warning in sorted(ingestion.warnings, key=lambda item: str(item["id"])):
            source_path = source_paths.get(
                str(warning["source_version_id"]), "unknown-source"
            )
            span = warning.get("span")
            if isinstance(span, Mapping):
                start = int(span["start_line"])
                end = int(span["end_line"])
                start_column = int(span["start_column"])
                end_column = "?" if span["end_column"] is None else str(span["end_column"])
                span_label = f"{start}:{start_column}-{end}:{end_column}"
            else:
                span_label = "unknown-span"
            possible_role = warning.get("possible_role") or "unknown"
            lines.append(
                f"- `{warning['code']}` at `{source_path}:{span_label}` "
                f"(possible role: {possible_role}): {warning['message']}"
            )
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def _current_reader(project: ProjectPaths) -> SnapshotReader | None:
    try:
        return SnapshotReader.open(project)
    except FileNotFoundError:
        return None


def _analysis_parent_snapshot_id(current: SnapshotReader | None) -> str | None:
    if current is None:
        return None
    if current.manifest.get("snapshot_kind") == "deterministic":
        return current.snapshot_id
    candidate = current.manifest.get("base_deterministic_snapshot_id")
    if not isinstance(candidate, str) or not candidate.startswith("deterministic:"):
        raise ValueError("selected layered snapshot has no base deterministic snapshot")
    return candidate


def _selected_material_is_fresh(
    current: SnapshotReader | None, material_digest: str
) -> bool:
    return (
        current is not None
        and current.manifest.get("material_input_digest") == material_digest
    )


@dataclass(frozen=True)
class RepositoryCapture:
    config: ProjectConfig
    inputs: tuple[SourceInput, ...]
    observation: dict[str, object]
    token: str


def _repository_capture(
    repository: Path,
    config_path: Path | None,
    observed_at: str | None,
    selected_paths: Sequence[str] = (".",),
) -> RepositoryCapture:
    selected_config, explicit = resolve_config_path(repository, config_path)
    try:
        config = load_config(repository, config_path)
    except ConfigurationPathError:
        raise
    except ValueError as error:
        raise ConfigurationPathError(f"invalid configuration: {error}") from error
    try:
        inputs = tuple(discover_sources(repository, config, selected_paths))
    except ValueError as error:
        raise RepositoryStateError(f"cannot capture repository sources: {error}") from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise RepositoryStateError("cannot capture repository sources") from error
    observation = capture_git_observation(repository, observed_at)
    try:
        config_file_state: dict[str, object] = (
            {"state": "absent", "content_digest": None}
            if not selected_config.exists() and not explicit
            else {
                "state": "present",
                "content_digest": sha256_digest(selected_config.read_bytes()),
            }
        )
    except OSError as error:
        raise ConfigurationPathError(
            f"cannot read configuration file: {selected_config}"
        ) from error
    token = sha256_digest(
        canonical_bytes(
            {
                "schema_version": 1,
                "config_path": selected_config.as_posix(),
                "config_file": config_file_state,
                "configuration_digest": configuration_digest(config),
                "sources": [
                    {
                        "path": item.relative_path,
                        "content_hash": item.content_hash,
                        "source_kind": item.source_kind,
                        "document_role": item.document_role,
                        "authority_class": item.authority_class,
                        "authority_basis": item.authority_basis,
                        "tracked": item.tracked,
                    }
                    for item in inputs
                ],
                "git": {
                    "branch": observation["branch"],
                    "commit": observation["commit"],
                    "dirty_fingerprint": observation["dirty_fingerprint"],
                },
            }
        )
    )
    return RepositoryCapture(config, inputs, observation, token)


def _stable_repository_capture(
    repository: Path,
    config_path: Path | None,
    observed_at: str | None,
    selected_paths: Sequence[str] = (".",),
) -> RepositoryCapture:
    first = _repository_capture(repository, config_path, observed_at, selected_paths)
    second = _repository_capture(repository, config_path, observed_at, selected_paths)
    if first.token != second.token:
        raise RepositoryStateError("repository changed while inputs were captured")
    return second


def _prepublication_observation(
    repository: Path,
    config_path: Path | None,
    observed_at: str | None,
    expected_token: str,
    selected_paths: Sequence[str] = (".",),
) -> dict[str, object]:
    final = _stable_repository_capture(
        repository, config_path, observed_at, selected_paths
    )
    if final.token != expected_token:
        raise RepositoryStateError("repository changed during indexing")
    return final.observation


def index_repository(
    root: Path,
    *,
    memory_root: Path | None = None,
    config_path: Path | None = None,
    observed_at: str | None = None,
    _selection: CorpusSelection | None = None,
) -> IndexResult:
    repository = root.resolve() if _selection is None else _selection.repository
    selected_paths = (".",) if _selection is None else _selection.inputs
    if _selection is not None and memory_root is None and not os.environ.get(
        "ARCHITECTURE_GRAPH_MEMORY_ROOT"
    ):
        check_default_memory_ignored(_selection)
    project = (
        ProjectPaths.resolve(repository, memory_root)
        if _selection is None
        else ProjectPaths.for_corpus(_selection, memory_root)
    )
    if _selection is not None:
        write_corpus_metadata(project, _selection)
    capture = _stable_repository_capture(
        repository, config_path, observed_at, selected_paths
    )
    config = capture.config
    inputs = capture.inputs
    config_digest = configuration_digest(config)
    pipeline = pipeline_fingerprint()
    pipeline_digest = pipeline.digest
    context = IngestionContext(
        config_digest, pipeline_digest, __version__, config.max_segment_chars
    )
    material_digest = material_input_digest(inputs, config, pipeline_digest)
    revision_digest = source_revision_digest(item.content_hash for item in inputs)
    current = _current_reader(project)
    expected_current = None if current is None else current.snapshot_id
    analysis_parent_id = _analysis_parent_snapshot_id(current)
    analysis_parent_reader = (
        None
        if analysis_parent_id is None
        else current
        if current is not None and current.snapshot_id == analysis_parent_id
        else SnapshotReader.open(project, analysis_parent_id)
    )
    prior_content_hashes = (
        {}
        if analysis_parent_reader is None
        else {
            str(item["path"]): str(item["content_hash"])
            for item in analysis_parent_reader.iter("sources")
        }
    )
    previous_commit = _selected_observation_commit(project, current, analysis_parent_id)
    current_content_hashes = {item.relative_path: item.content_hash for item in inputs}
    rename_resolution = _git_rename_resolution(
        repository,
        previous_commit,
        current_content_hashes,
        prior_content_hashes,
    ).relevant_to(set(current_content_hashes), set(prior_content_hashes))

    if _selected_material_is_fresh(current, material_digest):
        git_observation = _prepublication_observation(
            repository, config_path, observed_at, capture.token, selected_paths
        )
        published = observe_existing_snapshot(
            project, current, git_observation, current.snapshot_id
        )
        return IndexResult(
            snapshot_id=published.snapshot_id,
            observation_id=published.observation_id,
            reused=True,
            source_count=sum(1 for _ in current.iter("sources")),
            segment_count=sum(1 for _ in current.iter("segments")),
            warning_count=sum(1 for _ in current.iter("warnings")),
            selection=_selection,
        )

    input_digest = sha256_digest(
        canonical_bytes(
            {
                "material_input_digest": material_digest,
                "source_revision_digest": revision_digest,
                "analysis_parent_snapshot_id": analysis_parent_id,
                "rename_resolution": rename_resolution.as_digest_input(),
            }
        )
    )

    ingestion = ingest_sources(inputs, context)
    ingestion = ingestion.merge(
        _rename_resolution_warnings(inputs, rename_resolution, context)
    )
    logical_source_ids = _logical_source_ids(
        project,
        analysis_parent_reader,
        inputs,
        ingestion,
        rename_resolution,
    )
    sources, source_derivations = _source_records(
        inputs, ingestion, context, logical_source_ids
    )
    all_derivations = tuple(
        sorted(
            (*ingestion.derivations, *source_derivations),
            key=lambda item: str(item["id"]),
        )
    )
    records_by_type: dict[str, Sequence[Record]] = {
        "sources": sources,
        "segments": ingestion.segments,
        "evidence": ingestion.evidence,
        "derivations": all_derivations,
        "warnings": ingestion.warnings,
    }
    phase1_catalog = RecordCatalog.from_records(
        record for records in records_by_type.values() for record in records
    )
    analyzed = analyze_catalog(phase1_catalog).records_by_type()
    records_by_type = {
        record_type: analyzed.get(record_type, ())
        for record_type in RECORD_KIND_BY_TYPE
    }
    bundle = SnapshotBundle(
        snapshot_kind="deterministic",
        configuration_digest=config_digest,
        schema_versions={"snapshot": 1, "records": 1},
        frozen_review_set_digest=sha256_digest(b""),
        material_input_digest=material_digest,
        source_revision_digest=revision_digest,
        deterministic_pipeline_digest=pipeline_digest,
        pipeline_fingerprint=pipeline.preimage,
        input_digest=input_digest,
        analysis_parent_snapshot_id=analysis_parent_id,
        parent_snapshot_id=None,
        base_deterministic_snapshot_id=None,
        records_by_type=records_by_type,
        report=_report(sources, ingestion),
    )
    git_observation = _prepublication_observation(
        repository, config_path, observed_at, capture.token, selected_paths
    )
    published = publish_snapshot(
        project,
        bundle,
        git_observation,
        expected_current,
    )
    return IndexResult(
        snapshot_id=published.snapshot_id,
        observation_id=published.observation_id,
        reused=published.reused,
        source_count=len(sources),
        segment_count=len(ingestion.segments),
        warning_count=len(ingestion.warnings),
        selection=_selection,
    )


def index_corpus(
    paths: Sequence[Path],
    *,
    memory_root: Path | None = None,
    config_path: Path | None = None,
    observed_at: str | None = None,
) -> IndexResult:
    if not paths:
        raise ValueError("at least one corpus input is required")
    from architecture_graph.corpus import find_git_worktree

    repository = find_git_worktree(paths[0])
    selection = resolve_corpus(
        paths, configuration_identity(repository, config_path)
    )
    if memory_root is not None:
        check_memory_ignored(selection, memory_root)
    elif os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT"):
        check_memory_ignored(
            selection, Path(os.environ["ARCHITECTURE_GRAPH_MEMORY_ROOT"])
        )
    if memory_root is not None and selection.inputs == (".",):
        legacy = ProjectPaths.resolve(repository, memory_root)
        if legacy.current_path.is_file():
            result = index_repository(
                repository,
                memory_root=memory_root,
                config_path=config_path,
                observed_at=observed_at,
            )
            return replace(result, selection=selection)
    return index_repository(
        selection.repository,
        memory_root=memory_root,
        config_path=config_path,
        observed_at=observed_at,
        _selection=selection,
    )
