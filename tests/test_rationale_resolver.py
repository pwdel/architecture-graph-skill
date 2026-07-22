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


@pytest.mark.parametrize("roles", [("reason",)])
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


def test_different_alias_passages_in_one_parent_are_ambiguous(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"decision_log": [{"decision": "Use adapters", "context": "Centralize contracts", "justification": "Permit vendor switching"}]}))
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolution = resolve_rationales(reader).resolutions[0]
    assert resolution["classification"] == "ambiguous"
    assert resolution["resolves_diagnostics"] == []


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


def test_structured_rationale_never_crosses_source_pointer_collision(architecture_repo) -> None:
    directory = architecture_repo / "architecture"
    directory.mkdir()
    first = directory / "first.json"
    second = directory / "second.json"
    first.write_text(json.dumps({"decision_log": [{"decision": "Use adapters", "context": "Centralize contracts"}]}))
    second.write_text(json.dumps({"decision_log": [{"decision": "Use ports"}]}))
    git(architecture_repo, "add", "architecture")
    git(architecture_repo, "commit", "-m", "plans")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((first, second))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    by_statement = {
        next(item for item in reader.iter("decisions") if item["id"] == resolution["decision_id"])["statement"]: resolution
        for resolution in resolve_rationales(reader).resolutions
    }
    assert by_statement["Use adapters"]["classification"] == "recognized_alias"
    assert by_statement["Use ports"]["classification"] == "missing"


def test_decision_local_why_now_is_eligible(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"why_now": "Plan timing", "decision_log": [{"decision": "Use adapters", "why_now": "Avoid duplicated contracts"}]}))
    git(architecture_repo, "add", "architecture/plan.json")
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolution = resolve_rationales(reader).resolutions[0]
    assert resolution["classification"] == "recognized_alias"
    assert resolution["observed_roles"] == ["why_now"]


def test_conflicting_cross_source_rationales_are_ambiguous(architecture_repo) -> None:
    directory = architecture_repo / "architecture"
    directory.mkdir()
    first = directory / "first.json"
    second = directory / "second.json"
    first.write_text(json.dumps({"decision_log": [{"decision": "Use adapters", "context": "Centralize contracts"}]}))
    second.write_text(json.dumps({"decision_log": [{"decision": "Use adapters", "context": "Permit vendor switching"}]}))
    git(architecture_repo, "add", "architecture")
    git(architecture_repo, "commit", "-m", "plans")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((first, second))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolution = resolve_rationales(reader).resolutions[0]
    assert resolution["classification"] == "ambiguous"
    assert resolution["resolves_diagnostics"] == []


def test_markdown_rationale_is_bounded_to_its_decision_heading(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "decisions.md"
    path.parent.mkdir()
    path.write_text(
        "# ADR A\n\n## Decision\n\nFrontend must use adapters.\n\n"
        "## Rationale\n\nCentralize frontend contracts.\n\n"
        "# ADR B\n\n## Decision\n\nBackend must use ports.\n\n"
        "## Rationale\n\nKeep infrastructure replaceable.\n"
    )
    git(architecture_repo, "add", "architecture/decisions.md")
    git(architecture_repo, "commit", "-m", "adrs")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolutions = resolve_rationales(reader).resolutions
    assert len(resolutions) == 2
    evidence_texts = {
        resolution["decision_id"]: {
            reader.get("evidence", evidence_id)["text"]
            for evidence_id in resolution["evidence_ids"]
        }
        for resolution in resolutions
    }
    for decision in reader.iter("decisions"):
        expected = "Centralize frontend contracts." if "Frontend" in decision["statement"] else "Keep infrastructure replaceable."
        assert evidence_texts[decision["id"]] == {expected}
