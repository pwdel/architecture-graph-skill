from architecture_graph.nlp import normalize_evidence, parse_evidence
from architecture_graph.qualifiers import qualify_relations
from architecture_graph.relations import extract_relation_candidates
from tests.helpers.phase2_catalog import semantic_catalog


def test_prose_relation_is_qualified_before_claims() -> None:
    parsed = parse_evidence(normalize_evidence(semantic_catalog()))
    result = extract_relation_candidates(parsed)
    relation = qualify_relations(result.candidates, parsed)[0]
    assert relation.candidate.subject == "Checkout"
    assert relation.candidate.predicate == "publishes"
    assert relation.candidate.object == "OrderPlaced"
    assert relation.modality == "required"
    assert relation.applicability == "current"
