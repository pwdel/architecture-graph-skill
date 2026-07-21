from architecture_graph.nlp import normalize_evidence, parse_evidence
from helpers.phase2_catalog import semantic_catalog


def test_normalized_prose_retains_source_and_span() -> None:
    units = normalize_evidence(semantic_catalog())
    assert len(units) == 1
    assert units[0].path == "architecture.md"
    assert units[0].section_role == "decision"
    assert units[0].span["start_line"] == 4


def test_rule_parser_extracts_tokens_and_phrases() -> None:
    parsed = parse_evidence(normalize_evidence(semantic_catalog()))
    sentence = parsed.sentences[0]
    assert sentence.tokens == ("Checkout", "must", "publish", "OrderPlaced")
    assert "Checkout" in sentence.noun_phrases
    assert sentence.evidence_id == "evidence:one"
