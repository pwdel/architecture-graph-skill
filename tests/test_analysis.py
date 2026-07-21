from architecture_graph.analysis import analyze_catalog
from helpers.phase2_catalog import semantic_catalog


def test_analysis_runs_graph_before_decision_ranking() -> None:
    result = analyze_catalog(semantic_catalog())
    records = result.records_by_type()
    assert records["terms"]
    assert records["claims"]
    assert records["edges"]
    assert records["rankings"]
    assert records["decisions"]
