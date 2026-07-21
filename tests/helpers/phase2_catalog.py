from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.records import finalize_record


def semantic_catalog() -> RecordCatalog:
    derivation = finalize_record({"id": "derivation:fixture", "kind": "derivation"})
    source = finalize_record(
        {
            "id": "source:one", "kind": "source", "path": "architecture.md",
            "content_hash": "sha256:" + "1" * 64, "source_kind": "markdown",
            "document_role": "adr", "authority_class": "authoritative",
            "adr_metadata": {"status": "accepted"}, "adapter_name": "markdown",
        }
    )
    segment = finalize_record(
        {
            "id": "segment:one", "kind": "segment", "source_version_id": "source:one",
            "segment_kind": "paragraph", "heading_path": ["Decision"], "ordinal": 1,
            "text": "Checkout must publish OrderPlaced.",
            "span": {"start_line": 4, "end_line": 4, "start_column": 1, "end_column": 35},
            "metadata": {"section_role": "decision"}, "evidence_ids": ["evidence:one"],
            "derivation_ids": ["derivation:fixture"],
        }
    )
    evidence = finalize_record(
        {
            "id": "evidence:one", "kind": "evidence", "source_version_id": "source:one",
            "segment_id": "segment:one", "path": "architecture.md",
            "source_content_hash": "sha256:" + "1" * 64,
            "span": segment["span"], "text": segment["text"],
            "derivation_ids": ["derivation:fixture"],
        }
    )
    return RecordCatalog.from_records((derivation, source, segment, evidence))


def claimed_catalog() -> RecordCatalog:
    from architecture_graph.claims import materialize_claims
    from architecture_graph.entities import resolve_entities
    from architecture_graph.nlp import normalize_evidence, parse_evidence
    from architecture_graph.qualifiers import qualify_relations
    from architecture_graph.relations import extract_relation_candidates
    from architecture_graph.terms import discover_terms

    base = semantic_catalog()
    parsed = parse_evidence(normalize_evidence(base))
    terms = discover_terms(parsed)
    qualified = qualify_relations(extract_relation_candidates(parsed).candidates, parsed)
    entities = resolve_entities(qualified, terms)
    claims = materialize_claims(qualified, entities)
    records = (
        *base.all(), *parsed.derivations, *terms.terms, *terms.derivations,
        *entities.entities, *entities.derivations, *claims.claims, *claims.derivations,
    )
    return RecordCatalog.from_records(records)
