from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from architecture_graph.canonical import (
    atomic_write_json,
    canonical_bytes,
    canonical_dumps,
    sha256_digest,
)
from architecture_graph.cli import main
from architecture_graph.ingest import ingest_sources
from architecture_graph.jsonl_store import AtomicJsonlLedger, write_records
from architecture_graph.indexer import (
    IndexResult,
    RenameResolution,
    _analysis_parent_snapshot_id,
    _selected_material_is_fresh,
    _selected_observation_commit,
    index_repository,
)
from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths, RepositoryStateError
from architecture_graph.records import finalize_record
from architecture_graph.snapshot import SnapshotReader, publish_snapshot


def test_index_publishes_every_phase1_payload(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    result = index_repository(
        phase1_repository,
        memory_root=memory,
        observed_at="2026-07-19T10:00:00Z",
    )
    reader = SnapshotReader.open(ProjectPaths.resolve(phase1_repository, memory))
    assert result.snapshot_id == reader.snapshot_id
    assert result.source_count == 5
    assert result.segment_count > result.source_count
    assert {item["path"] for item in reader.iter("sources")} == {
        "architecture/deployment.puml",
        "architecture/interfaces.json",
        "architecture/notes.txt",
        "architecture/services.yaml",
        "docs/adr/ADR-001-events.md",
    }
    assert list(reader.iter("segments"))
    assert list(reader.iter("evidence"))
    assert list(reader.iter("derivations"))
    assert reader.manifest["pipeline_fingerprint"]
    assert sha256_digest(
        canonical_bytes(reader.manifest["pipeline_fingerprint"])
    ) == reader.manifest["deterministic_pipeline_digest"]
    assert reader.manifest["source_revision_digest"].startswith("sha256:")
    report = (reader.snapshot_dir / "report.md").read_text(encoding="utf-8")
    assert report.startswith("# Architecture Graph Ingestion\n")
    assert "2026-07-19" not in report
    for path in {
        "architecture/deployment.puml",
        "architecture/interfaces.json",
        "architecture/notes.txt",
        "architecture/services.yaml",
        "docs/adr/ADR-001-events.md",
    }:
        assert report.count(f"- `{path}`:") == 1


def test_index_corpus_indexes_explicit_design_json(architecture_repo: Path) -> None:
    from conftest import git, ignore_architecture_graph

    plan = architecture_repo / "lib" / "design" / "design-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        '{"title":"Plan","decision_log":[{"status":"accepted",'
        '"decision":"backend owns truth"}],"risks":["drift"]}'
    )
    git(architecture_repo, "add", "lib/design/design-plan.json")
    git(architecture_repo, "commit", "-m", "add design plan")
    ignore_architecture_graph(architecture_repo)
    result = index_corpus((plan,))
    project = ProjectPaths.for_corpus(result.selection)
    reader = SnapshotReader.open(project)
    assert result.corpus_id == result.selection.corpus_id
    assert [item["path"] for item in reader.iter("sources")] == [
        "lib/design/design-plan.json"
    ]
    assert any(
        item["metadata"].get("json_pointer") == "/decision_log/0/status"
        for item in reader.iter("segments")
    )


def test_index_corpus_requires_ignore_before_writing(architecture_repo: Path) -> None:
    from architecture_graph.corpus import MemoryNotIgnoredError

    with pytest.raises(MemoryNotIgnoredError):
        index_corpus((architecture_repo,))
    assert not (architecture_repo / ".architecture-graph").exists()


def test_cli_json_ignore_error_is_actionable(
    architecture_repo: Path, capsys
) -> None:
    assert main(["index", str(architecture_repo), "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error"]["code"] == "memory_not_ignored"
    assert payload["error"]["path"] == ".architecture-graph/"


def test_cli_index_status_find_get_workflow(architecture_repo: Path, capsys) -> None:
    from conftest import ignore_architecture_graph

    ignore_architecture_graph(architecture_repo)
    assert main(["index", str(architecture_repo), "--json"]) == 0
    indexed = json.loads(capsys.readouterr().out)
    corpus_id = indexed["corpus_id"]
    assert main(["memory", "status", str(architecture_repo), "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["items"][0]["state"] == "fresh"
    assert main(
        [
            "find", "segments", "--repo", str(architecture_repo),
            "--corpus", corpus_id, "--contains", "OrderPlaced", "--json",
        ]
    ) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["items"]
    segment_id = found["items"][0]["id"]
    assert main(
        [
            "get", "segments", segment_id, "--repo", str(architecture_repo),
            "--corpus", corpus_id, "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["id"] == segment_id


def test_cli_query_uses_environment_memory_root(
    architecture_repo: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    memory = tmp_path / "memory"
    monkeypatch.setenv("ARCHITECTURE_GRAPH_MEMORY_ROOT", str(memory))
    assert main(["index", str(architecture_repo), "--json"]) == 0
    indexed = json.loads(capsys.readouterr().out)
    assert main(
        [
            "find", "segments", "--repo", str(architecture_repo),
            "--corpus", indexed["corpus_id"], "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["items"]


def test_cli_reads_and_reuses_explicit_legacy_memory(
    architecture_repo: Path, tmp_path: Path, capsys
) -> None:
    memory = tmp_path / "legacy-memory"
    legacy = index_repository(architecture_repo, memory_root=memory)
    upgraded = index_corpus((architecture_repo,), memory_root=memory)
    assert upgraded.snapshot_id == legacy.snapshot_id
    assert main(
        [
            "find", "segments", "--repo", str(architecture_repo),
            "--memory-root", str(memory), "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["items"]
    assert main(
        [
            "find", "segments", "--repo", str(architecture_repo),
            "--memory-root", str(memory), "--corpus", "missing", "--json",
        ]
    ) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "corpus_not_found"


def test_in_repository_memory_override_must_be_ignored(
    architecture_repo: Path,
) -> None:
    from architecture_graph.corpus import MemoryNotIgnoredError

    memory = architecture_repo / "var" / "architecture-memory"
    with pytest.raises(MemoryNotIgnoredError, match="var/architecture-memory"):
        index_corpus((architecture_repo,), memory_root=memory)
    assert not memory.exists()


def test_recoverable_scalar_failure_marks_source_partial(
    phase1_repository: Path, tmp_path: Path
) -> None:
    structured = phase1_repository / "architecture" / "services.yaml"
    structured.write_text("good: orders\nbad: !!int nope\n")
    memory = tmp_path / "memory"
    result = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, memory), result.snapshot_id
    )
    record = next(
        item
        for item in reader.iter("sources")
        if item["path"] == "architecture/services.yaml"
    )
    assert record["parse_status"] == "partial"
    assert any(
        item["source_version_id"] == record["id"]
        for item in reader.iter("segments")
    )
    report = (reader.snapshot_dir / "report.md").read_text(encoding="utf-8")
    assert (
        "`parse_failed` at `architecture/services.yaml:2:1-2:?` "
        "(possible role: context)" in report
    )


def test_unchanged_material_reuses_snapshot_but_adds_observation(
    phase1_repository: Path, tmp_path: Path, monkeypatch
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(
        phase1_repository,
        memory_root=memory,
        observed_at="2026-07-19T10:00:00Z",
    )
    monkeypatch.setattr(
        "architecture_graph.indexer.ingest_sources",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unchanged index reran adapters")
        ),
    )
    second = index_repository(
        phase1_repository,
        memory_root=memory,
        observed_at="2026-07-19T11:00:00Z",
    )
    project = ProjectPaths.resolve(phase1_repository, memory)
    assert second.snapshot_id == first.snapshot_id
    assert second.reused is True
    assert len(project.observations_path.read_text().splitlines()) == 2
    observations = [
        json.loads(line) for line in project.observations_path.read_text().splitlines()
    ]
    assert all(
        item["source_revision_digest"]
        == SnapshotReader.open(project, first.snapshot_id).manifest[
            "source_revision_digest"
        ]
        for item in observations
    )


def test_staging_unchanged_working_bytes_reuses_matching_blob_provenance(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    adr = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    adr.write_text(adr.read_text() + "\nCheckout must retain events.\n")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    first_reader = SnapshotReader.open(project, first.snapshot_id)
    source = next(
        item
        for item in first_reader.iter("sources")
        if item["path"] == "docs/adr/ADR-001-events.md"
    )

    git(phase1_repository, "add", "docs/adr/ADR-001-events.md")
    staged_blob = git(
        phase1_repository, "rev-parse", ":docs/adr/ADR-001-events.md"
    ).strip()
    second = index_repository(phase1_repository, memory_root=memory)

    assert second.snapshot_id == first.snapshot_id
    assert second.reused is True
    assert source["git_blob"] == staged_blob


def test_changed_material_creates_analysis_parent(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(
        phase1_repository,
        memory_root=memory,
        observed_at="2026-07-19T10:00:00Z",
    )
    adr = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    adr.write_text(adr.read_text() + "\nCheckout must retain events for 30 days.\n")
    second = index_repository(
        phase1_repository,
        memory_root=memory,
        observed_at="2026-07-19T11:00:00Z",
    )
    reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, memory), second.snapshot_id
    )
    assert second.snapshot_id != first.snapshot_id
    assert reader.manifest["analysis_parent_snapshot_id"] == first.snapshot_id


def test_changed_material_bases_analysis_on_the_selected_layer_base() -> None:
    class ReviewedReader:
        snapshot_id = "reviewed:" + ("b" * 64)
        manifest = {
            "snapshot_kind": "reviewed",
            "base_deterministic_snapshot_id": "deterministic:" + ("a" * 64),
        }

    assert _analysis_parent_snapshot_id(ReviewedReader()) == (
        "deterministic:" + ("a" * 64)
    )


def test_identical_explicit_document_copy_shares_logical_source(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    original = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    duplicate = phase1_repository / "docs" / "adr" / "ADR-001-copy.md"
    duplicate.write_bytes(original.read_bytes())
    git(phase1_repository, "add", "docs/adr/ADR-001-copy.md")
    git(phase1_repository, "commit", "-m", "add exact ADR copy")
    memory = tmp_path / "memory"
    result = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, memory), result.snapshot_id
    )
    copies = [
        source
        for source in reader.iter("sources")
        if source["path"]
        in {
            "docs/adr/ADR-001-events.md",
            "docs/adr/ADR-001-copy.md",
        }
    ]
    assert len(copies) == 2
    assert len({source["id"] for source in copies}) == 2
    assert len({source["logical_source_id"] for source in copies}) == 1


def test_explicit_document_id_reused_for_different_bytes_fails(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    duplicate = phase1_repository / "docs" / "adr" / "ADR-001-conflict.md"
    duplicate.write_text(
        "---\nid: ADR-001\nstatus: proposed\n---\n\n"
        "# Different decision\n\nCheckout should use a shared database.\n"
    )
    git(phase1_repository, "add", "docs/adr/ADR-001-conflict.md")
    git(phase1_repository, "commit", "-m", "add conflicting ADR ID")
    with pytest.raises(
        ValueError, match="duplicate explicit document ID with different content"
    ):
        index_repository(phase1_repository, memory_root=tmp_path / "memory")


def test_path_fallback_logical_source_survives_unique_git_rename(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    note = phase1_repository / "docs" / "architecture" / "runtime.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# Runtime\n\nWorkers call the queue.\n")
    git(phase1_repository, "add", "docs/architecture/runtime.md")
    git(phase1_repository, "commit", "-m", "add runtime note")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    first_reader = SnapshotReader.open(project, first.snapshot_id)
    old = next(
        item
        for item in first_reader.iter("sources")
        if item["path"] == "docs/architecture/runtime.md"
    )

    git(
        phase1_repository,
        "mv",
        "docs/architecture/runtime.md",
        "docs/architecture/worker-runtime.md",
    )
    git(phase1_repository, "commit", "-m", "rename runtime note")
    second = index_repository(phase1_repository, memory_root=memory)
    second_reader = SnapshotReader.open(project, second.snapshot_id)
    renamed = next(
        item
        for item in second_reader.iter("sources")
        if item["path"] == "docs/architecture/worker-runtime.md"
    )
    assert renamed["logical_source_id"] == old["logical_source_id"]
    assert second_reader.manifest["input_digest"] == sha256_digest(
        canonical_bytes(
            {
                "material_input_digest": second_reader.manifest[
                    "material_input_digest"
                ],
                "source_revision_digest": second_reader.manifest[
                    "source_revision_digest"
                ],
                "analysis_parent_snapshot_id": first.snapshot_id,
                "rename_resolution": RenameResolution(
                    {
                        "docs/architecture/worker-runtime.md":
                        "docs/architecture/runtime.md"
                    },
                    {},
                    {},
                ).as_digest_input(),
            }
        )
    )


def test_dirty_parent_exact_digest_rename_preserves_logical_source(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    original = phase1_repository / "docs" / "architecture" / "runtime.md"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text("# Runtime\n\nCommitted wording.\n")
    git(phase1_repository, "add", "docs/architecture/runtime.md")
    git(phase1_repository, "commit", "-m", "add runtime")
    original.write_text("# Runtime\n\nDirty indexed wording.\n")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    first_reader = SnapshotReader.open(project, first.snapshot_id)
    prior = next(
        item
        for item in first_reader.iter("sources")
        if item["path"] == "docs/architecture/runtime.md"
    )

    git(
        phase1_repository,
        "mv",
        "docs/architecture/runtime.md",
        "docs/architecture/worker-runtime.md",
    )
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    renamed = next(
        item
        for item in reader.iter("sources")
        if item["path"] == "docs/architecture/worker-runtime.md"
    )
    assert renamed["content_hash"] == prior["content_hash"]
    assert renamed["logical_source_id"] == prior["logical_source_id"]


def test_dirty_parent_nonexact_rename_is_unresolved_not_commit_compared(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    original = phase1_repository / "docs" / "architecture" / "runtime.md"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text("# Runtime\n\nCommitted wording.\n")
    git(phase1_repository, "add", "docs/architecture/runtime.md")
    git(phase1_repository, "commit", "-m", "add runtime")
    original.write_text("# Runtime\n\nDirty indexed wording.\n")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    prior = SnapshotReader.open(project, first.snapshot_id)
    prior_source = next(
        item
        for item in prior.iter("sources")
        if item["path"] == "docs/architecture/runtime.md"
    )

    git(
        phase1_repository,
        "mv",
        "docs/architecture/runtime.md",
        "docs/architecture/worker-runtime.md",
    )
    target = phase1_repository / "docs" / "architecture" / "worker-runtime.md"
    target.write_text("# Worker Runtime\n\nChanged again after the rename.\n")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    renamed = next(
        item
        for item in reader.iter("sources")
        if item["path"] == "docs/architecture/worker-runtime.md"
    )
    assert renamed["logical_source_id"] != prior_source["logical_source_id"]
    warning = next(
        item for item in reader.iter("warnings") if item["code"] == "unresolved_rename"
    )
    assert "parent snapshot has no persisted raw bytes" in warning["message"]
    assert renamed["parse_status"] == "complete"
    assert reader.manifest["input_digest"] == sha256_digest(
        canonical_bytes(
            {
                "material_input_digest": reader.manifest["material_input_digest"],
                "source_revision_digest": reader.manifest["source_revision_digest"],
                "analysis_parent_snapshot_id": first.snapshot_id,
                "rename_resolution": RenameResolution(
                    {},
                    {},
                    {
                        "docs/architecture/worker-runtime.md": (
                            "docs/architecture/runtime.md",
                        )
                    },
                ).as_digest_input(),
            }
        )
    )


def test_reusing_a_path_after_a_rename_allocates_a_new_logical_source(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    original_path = phase1_repository / "docs" / "architecture" / "runtime.md"
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_text("# Runtime\n\nWorkers call the queue.\n")
    git(phase1_repository, "add", "docs/architecture/runtime.md")
    git(phase1_repository, "commit", "-m", "add runtime")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    first_reader = SnapshotReader.open(project, first.snapshot_id)
    first_source = next(
        item
        for item in first_reader.iter("sources")
        if item["path"] == "docs/architecture/runtime.md"
    )

    git(
        phase1_repository,
        "mv",
        "docs/architecture/runtime.md",
        "docs/architecture/worker-runtime.md",
    )
    git(phase1_repository, "commit", "-m", "move runtime")
    index_repository(phase1_repository, memory_root=memory)
    original_path.write_text("# New Runtime\n\nSchedulers call a different queue.\n")
    git(phase1_repository, "add", "docs/architecture/runtime.md")
    git(phase1_repository, "commit", "-m", "reuse old path")
    third = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, third.snapshot_id)
    by_path = {item["path"]: item for item in reader.iter("sources")}
    assert (
        by_path["docs/architecture/worker-runtime.md"]["logical_source_id"]
        == first_source["logical_source_id"]
    )
    assert (
        by_path["docs/architecture/runtime.md"]["logical_source_id"]
        != first_source["logical_source_id"]
    )


def test_ambiguous_rename_tie_becomes_add_remove_and_durable_warning(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    body = "# Runtime\n\nWorkers must use the queue.\n"
    old_paths = (
        "docs/architecture/runtime-a.md",
        "docs/architecture/runtime-b.md",
    )
    for relative_path in old_paths:
        path = phase1_repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    git(phase1_repository, "add", *old_paths)
    git(phase1_repository, "commit", "-m", "add tied rename origins")

    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    prior = SnapshotReader.open(project, first.snapshot_id)
    prior_ids = {
        item["path"]: item["logical_source_id"]
        for item in prior.iter("sources")
        if item["path"] in old_paths
    }

    git(phase1_repository, "rm", *old_paths)
    target = phase1_repository / "docs" / "architecture" / "tied.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    git(phase1_repository, "add", "docs/architecture/tied.md")
    git(phase1_repository, "commit", "-m", "replace tied origins")

    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    tied = next(
        item
        for item in reader.iter("sources")
        if item["path"] == "docs/architecture/tied.md"
    )
    assert tied["logical_source_id"] not in set(prior_ids.values())
    assert tied["parse_status"] == "complete"
    warning = next(
        item for item in reader.iter("warnings") if item["code"] == "ambiguous_rename"
    )
    assert warning["source_version_id"] == tied["id"]
    assert all(path in warning["message"] for path in old_paths)
    assert "treating it as an add/remove" in warning["message"]
    assert reader.manifest["input_digest"] == sha256_digest(
        canonical_bytes(
            {
                "material_input_digest": reader.manifest["material_input_digest"],
                "source_revision_digest": reader.manifest["source_revision_digest"],
                "analysis_parent_snapshot_id": first.snapshot_id,
                "rename_resolution": RenameResolution(
                    {},
                    {"docs/architecture/tied.md": old_paths},
                    {},
                ).as_digest_input(),
            }
        )
    )


def test_index_cli_returns_a_machine_envelope(
    phase1_repository: Path, tmp_path: Path, capsys
) -> None:
    assert main(
        [
            "index",
            str(phase1_repository),
            "--memory-root",
            str(tmp_path / "memory"),
            "--observed-at",
            "2026-07-19T10:00:00Z",
            "--json",
        ]
    ) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["snapshot_id"].startswith("deterministic:")
    assert payload["source_count"] == 5
    assert captured.out == canonical_dumps(payload) + "\n"
    assert captured.err == ""


def _source_at(reader: SnapshotReader, path: str) -> dict[str, object]:
    return next(item for item in reader.iter("sources") if item["path"] == path)


def _assert_rename_input_digest(
    reader: SnapshotReader,
    analysis_parent_snapshot_id: str,
    resolution: RenameResolution,
) -> None:
    assert reader.manifest["input_digest"] == sha256_digest(
        canonical_bytes(
            {
                "material_input_digest": reader.manifest["material_input_digest"],
                "source_revision_digest": reader.manifest["source_revision_digest"],
                "analysis_parent_snapshot_id": analysis_parent_snapshot_id,
                "rename_resolution": resolution.as_digest_input(),
            }
        )
    )


def test_configured_untracked_exact_rename_uses_manifest_delta(
    phase1_repository: Path, tmp_path: Path
) -> None:
    config = phase1_repository / ".architecture-graph.yaml"
    config.write_text(config.read_text() + "untracked:\n  - architecture/local.md\n")
    old_path = phase1_repository / "architecture" / "local.md"
    old_path.write_text("# Local runtime\n\nWorkers use the queue.\n")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    old = _source_at(
        SnapshotReader.open(project, first.snapshot_id), "architecture/local.md"
    )

    new_path = phase1_repository / "architecture" / "renamed-local.md"
    old_path.rename(new_path)
    config.write_text(
        config.read_text().replace(
            "architecture/local.md", "architecture/renamed-local.md"
        )
    )
    second = index_repository(phase1_repository, memory_root=memory)
    new = _source_at(
        SnapshotReader.open(project, second.snapshot_id),
        "architecture/renamed-local.md",
    )
    assert new["logical_source_id"] == old["logical_source_id"]


def test_same_transition_move_and_old_path_replacement_is_ambiguous(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    old_relative = "docs/architecture/runtime.md"
    new_relative = "docs/architecture/moved-runtime.md"
    old_path = phase1_repository / old_relative
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("# Runtime\n\nWorkers use the original queue.\n")
    git(phase1_repository, "add", old_relative)
    git(phase1_repository, "commit", "-m", "add runtime")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    parent = SnapshotReader.open(project, first.snapshot_id)
    parent_source = _source_at(parent, old_relative)

    git(phase1_repository, "mv", old_relative, new_relative)
    old_path.write_text("# Replacement\n\nWorkers use a replacement queue.\n")
    git(phase1_repository, "add", old_relative, new_relative)
    git(phase1_repository, "commit", "-m", "move and replace runtime")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    current = {
        path: _source_at(reader, path) for path in (old_relative, new_relative)
    }
    assert all(
        source["logical_source_id"] != parent_source["logical_source_id"]
        for source in current.values()
    )
    assert all(source["parse_status"] == "complete" for source in current.values())
    warnings = [
        item for item in reader.iter("warnings") if item["code"] == "ambiguous_rename"
    ]
    assert {item["source_version_id"] for item in warnings} == {
        current[old_relative]["id"],
        current[new_relative]["id"],
    }
    for path, source in current.items():
        expected_warning_ids = {
            item["id"]
            for item in warnings
            if item["source_version_id"] == source["id"]
        }
        assert expected_warning_ids.issubset(set(source["warning_ids"])), path
    resolution = RenameResolution(
        {},
        {
            new_relative: (old_relative,),
            old_relative: (old_relative,),
        },
        {},
    )
    _assert_rename_input_digest(reader, first.snapshot_id, resolution)


def test_no_added_overwrite_maps_continuity_and_exact_origins(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    p_relative = "docs/architecture/p.md"
    q_relative = "docs/architecture/q.md"
    p_path = phase1_repository / p_relative
    q_path = phase1_repository / q_relative
    p_path.parent.mkdir(parents=True, exist_ok=True)
    p_path.write_text("# P\n\nOriginal X bytes.\n")
    q_path.write_text("# Q\n\nOriginal Y bytes.\n")
    git(phase1_repository, "add", p_relative, q_relative)
    git(phase1_repository, "commit", "-m", "add overwrite origins")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    parent = SnapshotReader.open(project, first.snapshot_id)
    parent_ids = {
        _source_at(parent, path)["logical_source_id"]
        for path in (p_relative, q_relative)
    }

    q_bytes = q_path.read_bytes()
    git(phase1_repository, "rm", q_relative)
    p_path.write_bytes(q_bytes)
    git(phase1_repository, "add", p_relative)
    git(phase1_repository, "commit", "-m", "overwrite p with q bytes")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    current = _source_at(reader, p_relative)
    assert current["logical_source_id"] not in parent_ids
    assert current["parse_status"] == "complete"
    warnings = [
        item for item in reader.iter("warnings") if item["code"] == "ambiguous_rename"
    ]
    assert len(warnings) == 1
    assert warnings[0]["source_version_id"] == current["id"]
    assert warnings[0]["id"] in current["warning_ids"]
    resolution = RenameResolution(
        {},
        {p_relative: (p_relative, q_relative)},
        {},
    )
    _assert_rename_input_digest(reader, first.snapshot_id, resolution)


def test_byte_swap_records_complete_direct_candidate_map(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    p_relative = "docs/architecture/p.md"
    q_relative = "docs/architecture/q.md"
    p_path = phase1_repository / p_relative
    q_path = phase1_repository / q_relative
    p_path.parent.mkdir(parents=True, exist_ok=True)
    p_path.write_text("# P\n\nOriginal X bytes.\n")
    q_path.write_text("# Q\n\nOriginal Y bytes.\n")
    git(phase1_repository, "add", p_relative, q_relative)
    git(phase1_repository, "commit", "-m", "add swap origins")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    parent = SnapshotReader.open(project, first.snapshot_id)
    parent_ids = {
        _source_at(parent, path)["logical_source_id"]
        for path in (p_relative, q_relative)
    }

    p_bytes = p_path.read_bytes()
    q_bytes = q_path.read_bytes()
    p_path.write_bytes(q_bytes)
    q_path.write_bytes(p_bytes)
    git(phase1_repository, "add", p_relative, q_relative)
    git(phase1_repository, "commit", "-m", "swap source bytes")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    current = {
        path: _source_at(reader, path) for path in (p_relative, q_relative)
    }
    assert len({source["logical_source_id"] for source in current.values()}) == 2
    assert all(
        source["logical_source_id"] not in parent_ids for source in current.values()
    )
    assert all(source["parse_status"] == "complete" for source in current.values())
    warnings = [
        item for item in reader.iter("warnings") if item["code"] == "ambiguous_rename"
    ]
    assert len(warnings) == 2
    assert {item["source_version_id"] for item in warnings} == {
        current[p_relative]["id"],
        current[q_relative]["id"],
    }
    assert all(
        any(
            warning["id"] in source["warning_ids"]
            for warning in warnings
            if warning["source_version_id"] == source["id"]
        )
        for source in current.values()
    )
    origins = (p_relative, q_relative)
    resolution = RenameResolution(
        {},
        {p_relative: origins, q_relative: origins},
        {},
    )
    _assert_rename_input_digest(reader, first.snapshot_id, resolution)


def test_ordinary_same_path_edit_retains_continuity_without_warning(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    relative = "docs/architecture/continuity.md"
    path = phase1_repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Continuity\n\nOriginal bytes.\n")
    git(phase1_repository, "add", relative)
    git(phase1_repository, "commit", "-m", "add continuity source")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    parent = _source_at(SnapshotReader.open(project, first.snapshot_id), relative)

    path.write_text("# Continuity\n\nEdited bytes.\n")
    git(phase1_repository, "add", relative)
    git(phase1_repository, "commit", "-m", "edit continuity source")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    current = _source_at(reader, relative)
    assert current["logical_source_id"] == parent["logical_source_id"]
    assert current["parse_status"] == "complete"
    assert not any(
        item["code"] in {"ambiguous_rename", "unresolved_rename"}
        for item in reader.iter("warnings")
    )
    _assert_rename_input_digest(reader, first.snapshot_id, RenameResolution({}, {}, {}))


def test_unchanged_origin_copy_is_add_without_false_rename_warning(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    origin_relative = "docs/architecture/origin.md"
    copy_relative = "docs/architecture/copy.md"
    origin_path = phase1_repository / origin_relative
    copy_path = phase1_repository / copy_relative
    origin_path.parent.mkdir(parents=True, exist_ok=True)
    origin_path.write_text("# Shared bytes\n\nWorkers use the queue.\n")
    git(phase1_repository, "add", origin_relative)
    git(phase1_repository, "commit", "-m", "add unchanged origin")
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    parent = _source_at(
        SnapshotReader.open(project, first.snapshot_id), origin_relative
    )

    copy_path.write_bytes(origin_path.read_bytes())
    git(phase1_repository, "add", copy_relative)
    git(phase1_repository, "commit", "-m", "copy unchanged origin")
    second = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, second.snapshot_id)
    origin = _source_at(reader, origin_relative)
    copied = _source_at(reader, copy_relative)
    assert origin["logical_source_id"] == parent["logical_source_id"]
    assert copied["logical_source_id"] != parent["logical_source_id"]
    assert origin["parse_status"] == copied["parse_status"] == "complete"
    assert not any(
        item["code"] in {"ambiguous_rename", "unresolved_rename"}
        for item in reader.iter("warnings")
    )
    _assert_rename_input_digest(reader, first.snapshot_id, RenameResolution({}, {}, {}))


def test_orphan_observation_is_not_a_lineage_baseline(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    pointer = json.loads(project.current_path.read_text())
    selected = next(
        item
        for item in (
            json.loads(line)
            for line in project.observations_path.read_text().splitlines()
        )
        if item["id"] == pointer["observation_id"]
    )
    orphan = finalize_record(
        {
            **{key: value for key, value in selected.items() if key != "content_digest"},
            "id": "observation:orphan",
            "commit": "f" * 40,
        }
    )
    AtomicJsonlLedger(project.observations_path).append(orphan)
    reader = SnapshotReader.open(project, first.snapshot_id)
    assert (
        _selected_observation_commit(project, reader, first.snapshot_id)
        == selected["commit"]
    )


def test_selected_layer_observation_supplies_base_commit(
    phase1_repository: Path, tmp_path: Path
) -> None:
    digest = "sha256:" + "a" * 64
    deterministic_id = "deterministic:" + "b" * 64
    reviewed_id = "reviewed:" + "c" * 64
    project = ProjectPaths.resolve(phase1_repository, tmp_path / "memory")
    observation = finalize_record(
        {
            "id": "observation:selected-layer",
            "kind": "observation",
            "snapshot_id": reviewed_id,
            "previous_current_snapshot_id": deterministic_id,
            "base_deterministic_snapshot_id": deterministic_id,
            "material_input_digest": digest,
            "source_revision_digest": digest,
            "branch": "main",
            "commit": "d" * 40,
            "dirty_fingerprint": digest,
            "observed_at": "2026-07-19T10:00:00Z",
        }
    )
    write_records(project.observations_path, [observation])
    atomic_write_json(
        project.current_path,
        {
            "schema_version": 1,
            "snapshot_id": reviewed_id,
            "observation_id": observation["id"],
            "published_at": observation["observed_at"],
        },
    )
    reader = SimpleNamespace(
        snapshot_id=reviewed_id,
        manifest={
            "snapshot_kind": "reviewed",
            "base_deterministic_snapshot_id": deterministic_id,
            "material_input_digest": digest,
            "source_revision_digest": digest,
        },
    )
    assert _selected_observation_commit(project, reader, deterministic_id) == "d" * 40
    assert _selected_material_is_fresh(reader, digest) is True


def test_malformed_selected_observation_fails_before_lineage_or_pointer_change(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    before = project.current_path.read_bytes()
    pointer = json.loads(before)
    rows = [
        json.loads(line) for line in project.observations_path.read_text().splitlines()
    ]
    selected = next(item for item in rows if item["id"] == pointer["observation_id"])
    malformed = finalize_record(
        {
            **{key: value for key, value in selected.items() if key != "content_digest"},
            "commit": "not-a-commit",
        }
    )
    write_records(project.observations_path, [malformed])
    with pytest.raises(ValueError, match="lowercase SHA-1/SHA-256"):
        index_repository(phase1_repository, memory_root=memory)
    assert project.current_path.read_bytes() == before
    assert first.snapshot_id == pointer["snapshot_id"]


def test_selected_observation_missing_lineage_field_fails_closed(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    before = project.current_path.read_bytes()
    pointer = json.loads(before)
    selected = next(
        json.loads(line)
        for line in project.observations_path.read_text().splitlines()
        if json.loads(line)["id"] == pointer["observation_id"]
    )
    content = {
        key: value
        for key, value in selected.items()
        if key not in {"content_digest", "base_deterministic_snapshot_id"}
    }
    write_records(project.observations_path, [finalize_record(content)])
    with pytest.raises(ValueError, match="observation record is missing fields"):
        index_repository(phase1_repository, memory_root=memory)
    assert project.current_path.read_bytes() == before


def test_current_pointer_timestamp_must_match_selected_observation(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    pointer = json.loads(project.current_path.read_text())
    pointer["published_at"] = "2026-07-19T12:00:00Z"
    atomic_write_json(project.current_path, pointer)
    tampered = project.current_path.read_bytes()
    with pytest.raises(ValueError, match="timestamp does not match"):
        index_repository(phase1_repository, memory_root=memory)
    assert project.current_path.read_bytes() == tampered


def test_unresolved_rename_warning_does_not_make_parse_partial(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    old = phase1_repository / "docs" / "architecture" / "old.md"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("# Runtime\n\nWorkers use A.\n")
    git(phase1_repository, "add", "docs/architecture/old.md")
    git(phase1_repository, "commit", "-m", "add old")
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    git(phase1_repository, "mv", "docs/architecture/old.md", "docs/architecture/new.md")
    new = phase1_repository / "docs" / "architecture" / "new.md"
    new.write_text("# Runtime\n\nWorkers use B.\n")
    result = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, memory), result.snapshot_id
    )
    source = _source_at(reader, "docs/architecture/new.md")
    assert source["parse_status"] == "complete"
    assert any(item["code"] == "unresolved_rename" for item in reader.iter("warnings"))


def test_source_level_decode_failure_is_failed(
    phase1_repository: Path, tmp_path: Path
) -> None:
    path = phase1_repository / "architecture" / "services.yaml"
    path.write_bytes(b"good: value\n\xff")
    result = index_repository(phase1_repository, memory_root=tmp_path / "memory")
    reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, tmp_path / "memory"), result.snapshot_id
    )
    assert _source_at(reader, "architecture/services.yaml")["parse_status"] == "failed"


def test_selected_file_mutation_during_analysis_fails_without_pointer_change(
    phase1_repository: Path, tmp_path: Path, monkeypatch
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    before = project.current_path.read_bytes()
    selected = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    selected.write_text(selected.read_text() + "\nInitial material change.\n")
    real_ingest = ingest_sources

    def mutate_after_capture(*args, **kwargs):
        result = real_ingest(*args, **kwargs)
        path = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
        path.write_text(path.read_text() + "\nConcurrent mutation.\n")
        return result

    monkeypatch.setattr("architecture_graph.indexer.ingest_sources", mutate_after_capture)
    with pytest.raises(RepositoryStateError, match="changed during indexing"):
        index_repository(phase1_repository, memory_root=memory)
    assert project.current_path.read_bytes() == before
    assert SnapshotReader.open(project).snapshot_id == first.snapshot_id


def test_concurrent_changed_indexes_use_current_pointer_cas(
    phase1_repository: Path, tmp_path: Path, monkeypatch
) -> None:
    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    path = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    path.write_text(path.read_text() + "\nChanged once.\n")
    barrier = threading.Barrier(2)
    real_publish = publish_snapshot

    def synchronized_publish(*args, **kwargs):
        barrier.wait(timeout=10)
        return real_publish(*args, **kwargs)

    monkeypatch.setattr("architecture_graph.indexer.publish_snapshot", synchronized_publish)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                lambda _: _capture_index_outcome(phase1_repository, memory),
                range(2),
            )
        )
    assert sum(isinstance(item, IndexResult) for item in outcomes) == 1
    assert sum(isinstance(item, RuntimeError) for item in outcomes) == 1
    assert SnapshotReader.open(ProjectPaths.resolve(phase1_repository, memory)).manifest[
        "analysis_parent_snapshot_id"
    ] == first.snapshot_id


def _capture_index_outcome(root: Path, memory: Path) -> IndexResult | Exception:
    try:
        return index_repository(root, memory_root=memory)
    except Exception as error:
        return error


@pytest.mark.parametrize("change_after_move", [False, True])
def test_immediate_reindex_after_resolved_or_unresolved_rename_reuses(
    phase1_repository: Path, tmp_path: Path, change_after_move: bool
) -> None:
    from conftest import git

    old = phase1_repository / "docs" / "architecture" / "before.md"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("# Before\n\nWorkers use the queue.\n")
    git(phase1_repository, "add", "docs/architecture/before.md")
    git(phase1_repository, "commit", "-m", "add before")
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    git(
        phase1_repository,
        "mv",
        "docs/architecture/before.md",
        "docs/architecture/after.md",
    )
    if change_after_move:
        (phase1_repository / "docs" / "architecture" / "after.md").write_text(
            "# After\n\nWorkers use another queue.\n"
        )
    renamed = index_repository(phase1_repository, memory_root=memory)
    renamed_reader = SnapshotReader.open(
        ProjectPaths.resolve(phase1_repository, memory), renamed.snapshot_id
    )
    warning_codes = {item["code"] for item in renamed_reader.iter("warnings")}
    assert ("unresolved_rename" in warning_codes) is change_after_move
    repeated = index_repository(phase1_repository, memory_root=memory)
    assert repeated.snapshot_id == renamed.snapshot_id
    assert repeated.reused is True


def test_byte_identical_added_path_changes_material_not_source_revision(
    phase1_repository: Path, tmp_path: Path
) -> None:
    from conftest import git

    memory = tmp_path / "memory"
    first = index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    prior = SnapshotReader.open(project, first.snapshot_id)
    source = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    copy = phase1_repository / "docs" / "adr" / "ADR-001-copy.md"
    copy.write_bytes(source.read_bytes())
    git(phase1_repository, "add", "docs/adr/ADR-001-copy.md")
    git(phase1_repository, "commit", "-m", "add byte-identical copy")
    second = index_repository(phase1_repository, memory_root=memory)
    current = SnapshotReader.open(project, second.snapshot_id)
    assert second.snapshot_id != first.snapshot_id
    assert current.manifest["analysis_parent_snapshot_id"] == first.snapshot_id
    assert (
        current.manifest["material_input_digest"]
        != prior.manifest["material_input_digest"]
    )
    assert (
        current.manifest["source_revision_digest"]
        == prior.manifest["source_revision_digest"]
    )


def test_changed_then_reverted_bytes_create_child_of_current_parent(
    phase1_repository: Path, tmp_path: Path
) -> None:
    memory = tmp_path / "memory"
    project = ProjectPaths.resolve(phase1_repository, memory)
    path = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    original = path.read_bytes()
    first = index_repository(phase1_repository, memory_root=memory)
    path.write_bytes(original + b"\nTemporary change.\n")
    second = index_repository(phase1_repository, memory_root=memory)
    path.write_bytes(original)
    third = index_repository(phase1_repository, memory_root=memory)
    reader = SnapshotReader.open(project, third.snapshot_id)
    assert third.snapshot_id not in {first.snapshot_id, second.snapshot_id}
    assert reader.manifest["analysis_parent_snapshot_id"] == second.snapshot_id


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("config_case", ["missing", "directory"])
def test_explicit_config_cli_failure_is_stderr_only_and_preserves_pointer(
    phase1_repository: Path,
    tmp_path: Path,
    capsys,
    json_mode: bool,
    config_case: str,
) -> None:
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    before = project.current_path.read_bytes()
    selected = phase1_repository / "bad-config"
    if config_case == "directory":
        selected.mkdir()
    argv = [
        "index",
        str(phase1_repository),
        "--memory-root",
        str(memory),
        "--config",
        selected.name,
    ]
    if json_mode:
        argv.append("--json")
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    if json_mode:
        assert json.loads(captured.err)["error"]["code"] == "invalid_configuration"
    else:
        assert captured.err.startswith("architecture-graph: configuration ")
    assert "Traceback" not in captured.err
    assert project.current_path.read_bytes() == before


@pytest.mark.parametrize("json_mode", [False, True])
def test_non_repository_cli_failure_is_stderr_only(
    tmp_path: Path, capsys, json_mode: bool
) -> None:
    root = tmp_path / "not-a-repository"
    root.mkdir()
    argv = ["index", str(root), "--memory-root", str(tmp_path / "memory")]
    if json_mode:
        argv.append("--json")
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    if json_mode:
        assert json.loads(captured.err)["error"]["code"] == "invalid_request"
    else:
        assert captured.err.startswith("architecture-graph: ")
    assert "Traceback" not in captured.err
    assert not (tmp_path / "memory").exists()


@pytest.mark.parametrize("json_mode", [False, True])
def test_file_valued_memory_root_is_stderr_only(
    phase1_repository: Path, tmp_path: Path, capsys, json_mode: bool
) -> None:
    memory_file = tmp_path / "memory-file"
    memory_file.write_bytes(b"sentinel")
    argv = [
        "index",
        str(phase1_repository),
        "--memory-root",
        str(memory_file),
    ]
    if json_mode:
        argv.append("--json")
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    if json_mode:
        assert json.loads(captured.err)["error"]["code"] == "invalid_request"
    else:
        assert "Not a directory" in captured.err
    assert len(captured.err.splitlines()) == 1
    assert memory_file.read_bytes() == b"sentinel"


@pytest.mark.parametrize("json_mode", [False, True])
def test_unwritable_memory_root_is_stderr_only_and_preserves_pointer(
    phase1_repository: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
    json_mode: bool,
) -> None:
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    pointer_before = project.current_path.read_bytes()
    adr = phase1_repository / "docs" / "adr" / "ADR-001-events.md"
    adr.write_text(adr.read_text() + "\nChanged material.\n")

    def deny_write(*args, **kwargs):
        raise PermissionError("simulated unwritable memory root")

    monkeypatch.setattr("architecture_graph.snapshot._write_stage", deny_write)
    argv = [
        "index",
        str(phase1_repository),
        "--memory-root",
        str(memory),
    ]
    if json_mode:
        argv.append("--json")
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    if json_mode:
        assert json.loads(captured.err)["error"]["code"] == "permission_denied"
    else:
        assert "permission denied during filesystem operation" in captured.err
    assert len(captured.err.splitlines()) == 1
    assert project.current_path.read_bytes() == pointer_before


def test_index_cli_human_success_uses_stdout_only(
    phase1_repository: Path, tmp_path: Path, capsys
) -> None:
    assert main(
        [
            "index",
            str(phase1_repository),
            "--memory-root",
            str(tmp_path / "memory"),
        ]
    ) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Indexed 5 sources into deterministic:")
    assert captured.err == ""


def test_unreadable_explicit_config_never_falls_back(
    phase1_repository: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    memory = tmp_path / "memory"
    index_repository(phase1_repository, memory_root=memory)
    project = ProjectPaths.resolve(phase1_repository, memory)
    before = project.current_path.read_bytes()
    selected = phase1_repository / "selected.yaml"
    selected.write_text("schema_version: 1\n")
    real_read_text = Path.read_text

    def denied(path: Path, *args, **kwargs):
        if path == selected.resolve():
            raise PermissionError("denied")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    assert main(
        [
            "index",
            str(phase1_repository),
            "--memory-root",
            str(memory),
            "--config",
            "selected.yaml",
            "--json",
        ]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "cannot read configuration file" in captured.err
    assert project.current_path.read_bytes() == before
