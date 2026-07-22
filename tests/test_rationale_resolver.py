import json

import pytest

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


@pytest.mark.parametrize("roles", [("reason",), ("context", "justification")])
def test_structured_aliases_are_compatible(architecture_repo, roles) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    decision = {"title": "Adapter", "status": "accepted", "decision": "Use adapters"}
    decision.update({role: f"Evidence for {role}" for role in roles})
    path.write_text(json.dumps({"decision_log": [decision]}))
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolution = resolve_rationales(reader).resolutions[0]
    assert resolution["classification"] == "recognized_alias"
    assert resolution["observed_roles"] == sorted(roles)


def test_markdown_rationale_section_resolves_single_adr(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "adr.md"
    path.parent.mkdir()
    path.write_text(
        "---\nstatus: accepted\n---\n# Adapter decision\n\n"
        "## Decision\n\nFrontend must use API adapters.\n\n"
        "## Rationale\n\nAdapters centralize contract translation.\n"
    )
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "adr")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolution = resolve_rationales(reader).resolutions[0]
    assert resolution["classification"] == "explicit"
    assert resolution["observed_roles"] == ["rationale"]
    assert resolution["evidence_ids"]
