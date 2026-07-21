from architecture_graph.nlp import normalize_evidence, parse_evidence
from architecture_graph.terms import discover_terms
from helpers.phase2_catalog import semantic_catalog


def test_terms_are_source_backed_and_ranked() -> None:
    parsed = parse_evidence(normalize_evidence(semantic_catalog()))
    result = discover_terms(parsed)
    checkout = next(item for item in result.terms if item["canonical_form"] == "checkout")
    assert checkout["distinct_source_count"] == 1
    assert checkout["tfidf"] > 0
    assert checkout["evidence_ids"] == ["evidence:one"]
