from architecture_graph.ranking import rank_graph
from architecture_graph.semantic_graph import build_evidence_graph
from helpers.phase2_catalog import claimed_catalog


def test_rankings_contain_four_independent_explainable_scores() -> None:
    catalog = claimed_catalog()
    result = rank_graph(build_evidence_graph(catalog), catalog)
    assert result.rankings
    for ranking in result.rankings:
        assert set(ranking["scores"]) == {
            "navigation", "criticality", "review_priority", "extraction_confidence"
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
