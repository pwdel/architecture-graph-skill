import json

from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.rationale_resolver import resolve_rationales
from architecture_graph.snapshot import SnapshotReader
from conftest import git, ignore_architecture_graph


def test_context_sibling_resolves_missing_rationale(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"decision_log": [{"title": "Adapter", "status": "accepted", "decision": "Use adapters", "context": "Centralize contracts"}]}))
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    result = resolve_rationales(reader)
    assert len(result.resolutions) == 1
    assert result.resolutions[0]["classification"] == "recognized_alias"
    assert result.resolutions[0]["observed_roles"] == ["context"]
    assert result.resolutions[0]["resolves_diagnostics"] == ["missing_rationale"]
