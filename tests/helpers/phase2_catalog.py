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
