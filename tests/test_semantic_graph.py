from architecture_graph.semantic_graph import bounded_neighbors, build_evidence_graph
from helpers.phase2_catalog import claimed_catalog


def test_every_graph_edge_has_provenance_and_valid_endpoints() -> None:
    graph = build_evidence_graph(claimed_catalog())
    ids = {item["id"] for item in graph.nodes}
    assert graph.edges
    for edge in graph.edges:
        assert edge["from_id"] in ids
        assert edge["to_id"] in ids
        assert edge["evidence_ids"] or edge["derivation_ids"]


def test_neighbors_are_bounded_and_cycle_safe() -> None:
    graph = build_evidence_graph(claimed_catalog())
    entity = next(item["id"] for item in graph.nodes if item["kind"] == "entity")
    result = bounded_neighbors(graph, entity, depth=2, limit=20)
    assert result.nodes
    assert max(item["depth"] for item in result.nodes) <= 2
    assert len({item["id"] for item in result.nodes}) == len(result.nodes)
