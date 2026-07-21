from pathlib import Path

import pytest

from architecture_graph.corpus import (
    MemoryNotIgnoredError,
    check_default_memory_ignored,
    resolve_corpus,
    validate_corpus_metadata,
    write_corpus_metadata,
)
from architecture_graph.project import ProjectPaths


def test_corpus_normalizes_order_overlap_and_content_changes(
    architecture_repo: Path,
) -> None:
    directory = architecture_repo / "docs"
    file = directory / "adr" / "ADR-001.md"
    first = resolve_corpus([file, directory], "config:one")
    file.write_text(file.read_text() + "\nChanged.\n")
    second = resolve_corpus([directory, file], "config:one")
    assert first.inputs == second.inputs == ("docs",)
    assert second.corpus_id == first.corpus_id


def test_corpus_identity_changes_with_inputs_and_config(
    architecture_repo: Path,
) -> None:
    file = architecture_repo / "docs" / "adr" / "ADR-001.md"
    by_file = resolve_corpus([file], "config:one")
    by_repo = resolve_corpus([architecture_repo], "config:one")
    changed_config = resolve_corpus([file], "config:two")
    assert len({by_file.corpus_id, by_repo.corpus_id, changed_config.corpus_id}) == 3


def test_corpus_rejects_cross_repository_and_missing_paths(
    architecture_repo: Path, tmp_path: Path
) -> None:
    from conftest import git

    second = tmp_path / "second"
    second.mkdir()
    git(second, "init", "-b", "main")
    foreign = second / "architecture.json"
    foreign.write_text("{}")
    with pytest.raises(ValueError, match="same Git worktree"):
        resolve_corpus([architecture_repo, foreign], "config:one")
    with pytest.raises(ValueError, match="does not exist"):
        resolve_corpus([architecture_repo / "missing.json"], "config:one")


def test_default_memory_is_corpus_scoped_and_requires_ignore(
    architecture_repo: Path,
) -> None:
    selection = resolve_corpus([architecture_repo], "config:one")
    with pytest.raises(MemoryNotIgnoredError, match=".architecture-graph/"):
        check_default_memory_ignored(selection)
    assert not (architecture_repo / ".architecture-graph").exists()


def test_memory_precedence_and_metadata_round_trip(
    architecture_repo: Path, tmp_path: Path, monkeypatch
) -> None:
    from conftest import ignore_architecture_graph

    ignore_architecture_graph(architecture_repo)
    selection = resolve_corpus([architecture_repo], "config:one")
    default = ProjectPaths.for_corpus(selection)
    assert default.project_dir == (
        architecture_repo / ".architecture-graph" / "corpora" / selection.corpus_id
    )
    monkeypatch.setenv("ARCHITECTURE_GRAPH_MEMORY_ROOT", str(tmp_path / "env"))
    assert ProjectPaths.for_corpus(selection).projects_root == tmp_path / "env" / "corpora"
    explicit = ProjectPaths.for_corpus(selection, tmp_path / "cli")
    assert explicit.projects_root == tmp_path / "cli" / "corpora"
    write_corpus_metadata(explicit, selection)
    before = explicit.corpus_file.read_bytes()
    validate_corpus_metadata(explicit, selection)
    changed = resolve_corpus([architecture_repo], "config:two")
    with pytest.raises(ValueError, match="corpus metadata"):
        validate_corpus_metadata(explicit, changed)
    assert explicit.corpus_file.read_bytes() == before
