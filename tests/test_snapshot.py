from pathlib import Path

import pytest

from architecture_graph.canonical import (
    canonical_bytes,
    sha256_digest,
    source_revision_digest,
)
from architecture_graph.project import ProjectPaths
from architecture_graph.records import finalize_record
from architecture_graph.snapshot import (
    SnapshotBundle,
    SnapshotFinalizer,
    SnapshotReader,
    observe_existing_snapshot,
    publish_snapshot,
)


CONFIG_DIGEST = "sha256:" + "a" * 64
PIPELINE_PREIMAGE = {
    "schema_version": 1,
    "runtime": {
        "implementation": "CPython",
        "python_version": "3.12.0",
        "cache_tag": "cpython-312",
    },
    "files": {"adapter.py": "sha256:" + ("1" * 64)},
    "packages": {"PyYAML": "6.0.2", "jmespath": "1.1.0", "jsonlines": "4.0.0"},
}
PIPELINE_DIGEST = sha256_digest(canonical_bytes(PIPELINE_PREIMAGE))
CONTENT_DIGEST = "sha256:" + "c" * 64
EMPTY_REVIEWS_DIGEST = "sha256:" + "d" * 64
MATERIAL_DIGEST = "sha256:" + "e" * 64
SOURCE_REVISION_DIGEST = source_revision_digest([CONTENT_DIGEST])
INPUT_DIGEST = "sha256:" + "f" * 64


def bundle(path: str = "docs/adr/ADR-001.md") -> SnapshotBundle:
    source_id = f"source:{path}"
    derivation = finalize_record(
        {
            "id": "derivation:source-manifest",
            "kind": "derivation",
            "producer_kind": "deterministic",
            "method": "source_manifest",
            "tool": "architecture-graph",
            "tool_version": "0.1.0",
            "model": None,
            "model_version": None,
            "model_artifact_digest": None,
            "configuration_digest": CONFIG_DIGEST,
            "pipeline_digest": PIPELINE_DIGEST,
            "input_ids": [source_id],
            "output_kind": "source",
            "output_identity_key": source_id,
            "created_at": None,
        }
    )
    source = finalize_record(
        {
            "id": source_id,
            "kind": "source",
            "logical_source_id": f"logical-source:{path}",
            "path": path,
            "source_kind": "markdown",
            "document_role": "adr",
            "authority_class": "accepted_adr_or_active_standard",
            "authority_basis": "adr_status",
            "tracked": True,
            "git_blob": "fixture-blob",
            "content_hash": CONTENT_DIGEST,
            "decodable": True,
            "adr_metadata": {"id": "ADR-001", "status": "accepted"},
            "adapter_name": "markdown",
            "adapter_version": "v1",
            "parse_status": "complete",
            "warning_ids": [],
            "configuration_digest": CONFIG_DIGEST,
            "deterministic_pipeline_digest": PIPELINE_DIGEST,
            "derivation_ids": [derivation["id"]],
        }
    )
    return SnapshotBundle(
        snapshot_kind="deterministic",
        configuration_digest=CONFIG_DIGEST,
        schema_versions={"snapshot": 1, "records": 1},
        frozen_review_set_digest=EMPTY_REVIEWS_DIGEST,
        material_input_digest=MATERIAL_DIGEST,
        source_revision_digest=SOURCE_REVISION_DIGEST,
        deterministic_pipeline_digest=PIPELINE_DIGEST,
        pipeline_fingerprint=PIPELINE_PREIMAGE,
        input_digest=INPUT_DIGEST,
        analysis_parent_snapshot_id=None,
        parent_snapshot_id=None,
        base_deterministic_snapshot_id=None,
        records_by_type={"sources": [source], "derivations": [derivation]},
        report="# Ingestion\n\nOne source.\n",
    )


def observation(observed_at: str) -> dict[str, object]:
    return {
        "branch": "main",
        "commit": "abc123",
        "dirty_fingerprint": CONFIG_DIGEST,
        "observed_at": observed_at,
    }


def test_observation_time_does_not_change_snapshot_identity(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    first = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    second = publish_snapshot(
        project,
        bundle(),
        observation("2026-07-19T11:00:00Z"),
        first.snapshot_id,
    )
    assert second.snapshot_id == first.snapshot_id
    assert second.snapshot_id.startswith("deterministic:")
    assert len(list((project.observations_path).read_text().splitlines())) == 2
    assert "2026-07-19" not in (first.snapshot_dir / "report.md").read_text()


def test_reader_defaults_to_current_and_is_read_only(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    reader = SnapshotReader.open(project)
    assert reader.snapshot_id == published.snapshot_id
    assert reader.get("sources", "source:docs/adr/ADR-001.md")["path"] == "docs/adr/ADR-001.md"


def test_stale_expected_current_cannot_replace_pointer(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    first = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    with pytest.raises(RuntimeError, match="current snapshot changed"):
        publish_snapshot(
            project,
            bundle("docs/adr/ADR-002.md"),
            observation("2026-07-19T11:00:00Z"),
            None,
        )
    assert SnapshotReader.open(project).snapshot_id == first.snapshot_id


def test_existing_digest_with_different_payload_is_fatal(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    (published.snapshot_dir / "sources.jsonl").write_text("corrupt\n")
    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, published.snapshot_id)
    with pytest.raises(ValueError, match="collision"):
        publish_snapshot(
            project,
            bundle(),
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_collision_rejects_unexpected_directories(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    (published.snapshot_dir / "unexpected").mkdir()
    with pytest.raises(ValueError, match="collision"):
        publish_snapshot(
            project,
            bundle(),
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_invalid_snapshot_id_and_unknown_payload_type_fail_closed(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    with pytest.raises(ValueError, match="invalid snapshot ID"):
        SnapshotReader.open(project, "deterministic:../../escape")
    invalid = bundle()
    invalid = SnapshotBundle(
        **{**invalid.__dict__, "records_by_type": {"soruces": []}}
    )
    with pytest.raises(ValueError, match="unknown snapshot record types"):
        publish_snapshot(project, invalid, observation("2026-07-19T10:00:00Z"), None)


def test_phase1_writer_rejects_layered_kinds_and_fingerprint_mismatch(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    layered = SnapshotBundle(**{**bundle().__dict__, "snapshot_kind": "reviewed"})
    with pytest.raises(ValueError, match="Phase 1 publishes deterministic"):
        publish_snapshot(
            project, layered, observation("2026-07-19T10:00:00Z"), None
        )

    mismatched = SnapshotBundle(
        **{
            **bundle().__dict__,
            "pipeline_fingerprint": {
                **PIPELINE_PREIMAGE,
                "packages": {"PyYAML": "different"},
            },
        }
    )
    with pytest.raises(ValueError, match="pipeline fingerprint"):
        publish_snapshot(
            project, mismatched, observation("2026-07-19T10:00:00Z"), None
        )


def test_false_source_revision_fails_validation_and_publication_without_pointer_change(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    current_before = project.current_path.read_bytes()
    wrong_digest = "sha256:" + ("8" * 64)
    assert wrong_digest != SOURCE_REVISION_DIGEST
    invalid = SnapshotBundle(
        **{**bundle().__dict__, "source_revision_digest": wrong_digest}
    )

    with pytest.raises(ValueError, match="source revision digest mismatch"):
        SnapshotFinalizer(project, invalid).validate()
    with pytest.raises(ValueError, match="source revision digest mismatch"):
        publish_snapshot(
            project,
            invalid,
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )

    assert project.current_path.read_bytes() == current_before
    assert SnapshotReader.open(project).snapshot_id == published.snapshot_id


def test_exact_duplicate_is_deduplicated_but_conflict_is_rejected(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    source = original.records_by_type["sources"][0]
    duplicate = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [source, source],
            },
        }
    )
    published = publish_snapshot(
        project, duplicate, observation("2026-07-19T10:00:00Z"), None
    )
    assert len(list(SnapshotReader.open(project).iter("sources"))) == 1

    conflicting_record = dict(source)
    conflicting_record["path"] = "docs/adr/ADR-002.md"
    conflicting = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [source, finalize_record(conflicting_record)]
            },
        }
    )
    with pytest.raises(ValueError, match="conflicting duplicate"):
        publish_snapshot(
            project,
            conflicting,
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_broken_references_fail_before_publication(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    source = dict(original.records_by_type["sources"][0])
    source["warning_ids"] = ["warning:missing"]
    broken = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [finalize_record(source)],
            },
        }
    )
    with pytest.raises(ValueError, match="broken reference"):
        publish_snapshot(
            project, broken, observation("2026-07-19T10:00:00Z"), None
        )
    assert not project.current_path.exists()
