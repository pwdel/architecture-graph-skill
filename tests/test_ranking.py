from architecture_graph.ranking import rank_graph
from architecture_graph.semantic_graph import build_evidence_graph
from helpers.phase2_catalog import claimed_catalog


def test_rankings_contain_independent_explainable_scores() -> None:
    catalog = claimed_catalog()
    result = rank_graph(build_evidence_graph(catalog), catalog)
    assert result.rankings
    for ranking in result.rankings:
        assert set(ranking["scores"]) == {
            "navigation", "criticality", "review_priority", "extraction_confidence",
            "corroboration", "completeness",
        }
        for score in ranking["scores"].values():
            assert 0 <= score["score"] <= 1
            assert score["features"]


def test_navigation_exposes_deterministic_pagerank_and_lexical_features() -> None:
    catalog = claimed_catalog()
    result = rank_graph(build_evidence_graph(catalog), catalog)
    term_ranking = next(
        item for item in result.rankings
        if catalog.get(str(item["node_id"]))["kind"] == "term"
    )
    features = term_ranking["scores"]["navigation"]["features"]
    assert "pagerank" in features
    assert "lexical_salience" in features
    assert 0 <= features["pagerank"] <= 1


def test_extraction_confidence_does_not_imply_criticality() -> None:
    catalog = claimed_catalog()
    graph = build_evidence_graph(catalog)
    result = rank_graph(graph, catalog)
    decision_like = next(item for item in result.rankings if catalog.get(str(item["node_id"]))["kind"] == "claim")
    scores = decision_like["scores"]
    assert scores["extraction_confidence"]["score"] != scores["criticality"]["score"]
