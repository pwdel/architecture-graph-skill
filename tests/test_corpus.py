from pathlib import Path

import pytest

from architecture_graph.corpus import resolve_corpus


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
