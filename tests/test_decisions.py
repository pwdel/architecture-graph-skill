from architecture_graph.decisions import attach_decisions, reduce_decisions
from architecture_graph.semantic_graph import build_evidence_graph
from helpers.phase2_catalog import claimed_catalog


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
