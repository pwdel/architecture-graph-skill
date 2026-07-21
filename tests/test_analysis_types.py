import pytest

from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.records import finalize_record
from architecture_graph.schemas import (
    load_versioned_resource,
    resource_digest,
    validate_typed_record,
)


def test_catalog_deduplicates_identical_records() -> None:
    record = finalize_record({"id": "term:gateway", "kind": "term"})
    catalog = RecordCatalog.from_records((record, record))
    assert catalog.iter("term") == (record,)


def test_catalog_rejects_one_id_with_different_content() -> None:
    first = finalize_record({"id": "term:gateway", "kind": "term", "value": 1})
    second = finalize_record({"id": "term:gateway", "kind": "term", "value": 2})
    with pytest.raises(ValueError, match="duplicate record id with different content"):
        RecordCatalog.from_records((first, second))


def test_typed_term_requires_evidence_and_derivations() -> None:
    record = finalize_record(
        {
            "id": "term:gateway",
            "kind": "term",
            "canonical_form": "gateway",
            "observed_forms": ["Gateway"],
            "term_kind": "noun_phrase",
            "distinct_source_count": 1,
            "document_frequency": 1,
            "tfidf": 1.0,
            "discovery_signals": ["tfidf"],
        }
    )
    assert {issue.field for issue in validate_typed_record(record, "term")} == {
        "evidence_ids",
        "derivation_ids",
    }


def test_versioned_resources_have_stable_digests() -> None:
    resource = load_versioned_resource("predicates-v1.json")
    assert resource["schema_version"] == 1
    assert resource_digest("predicates-v1.json") == resource_digest(
        "predicates-v1.json"
    )
