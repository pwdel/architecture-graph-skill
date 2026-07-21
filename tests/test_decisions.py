from architecture_graph.decisions import attach_decisions, reduce_decisions
from architecture_graph.semantic_graph import build_evidence_graph
from helpers.phase2_catalog import claimed_catalog
from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader
import json


def test_decision_reduction_preserves_status_and_source_evidence() -> None:
    catalog = claimed_catalog()
    graph = build_evidence_graph(catalog)
    result = reduce_decisions(catalog, graph)
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision["status"] == "accepted"
    assert decision["applicability"] == "current"
    assert decision["evidence_ids"] == ["evidence:one"]
    assert attach_decisions(graph, result).nodes[-1]["kind"] in {"decision", "term"}


def test_json_decision_log_siblings_reduce_to_decisions(architecture_repo) -> None:
    from conftest import git, ignore_architecture_graph

    path = architecture_repo / "architecture" / "design-plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"decision_log": [
        {"title": "Adapter boundary", "status": "accepted", "decision": "Frontend requests must use the API adapter.", "rationale": "Centralizes contract handling."},
        {"title": "Test gate", "status": "proposed", "decision": "Declare test tooling before adding a CI gate."},
    ]}))
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "add decision log")
    ignore_architecture_graph(architecture_repo)
    result = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    decisions = tuple(sorted(reader.iter("decisions"), key=lambda item: item["title"]))
    assert [item["title"] for item in decisions] == ["Adapter boundary", "Test gate"]
    assert [item["status"] for item in decisions] == ["accepted", "proposed"]
    assert decisions[0]["rationale_evidence_ids"]
