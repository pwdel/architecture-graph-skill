from architecture_graph.claims import materialize_claims
from architecture_graph.entities import resolve_entities
from architecture_graph.nlp import normalize_evidence, parse_evidence
from architecture_graph.qualifiers import qualify_relations
from architecture_graph.relations import extract_relation_candidates
from architecture_graph.terms import discover_terms
from helpers.phase2_catalog import semantic_catalog


def test_complete_relation_creates_source_backed_claim() -> None:
    parsed = parse_evidence(normalize_evidence(semantic_catalog()))
    terms = discover_terms(parsed)
    qualified = qualify_relations(extract_relation_candidates(parsed).candidates, parsed)
    entities = resolve_entities(qualified, terms)
    result = materialize_claims(qualified, entities)
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim["predicate"] == "publishes"
    assert claim["evidence_ids"] == ["evidence:one"]
    assert claim["qualifiers"]["modality"] == "required"
