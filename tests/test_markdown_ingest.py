from pathlib import Path

from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.records import validate_record_shape
from architecture_graph.sources import SourceInput


FIXTURE = Path(__file__).parent / "fixtures" / "phase1_repo" / "docs" / "adr" / "ADR-001-events.md"


def fixture_source() -> SourceInput:
    text = FIXTURE.read_text(encoding="utf-8")
    return SourceInput(
        relative_path="docs/adr/ADR-001-events.md",
        absolute_path=FIXTURE,
        source_kind="markdown",
        document_role="adr",
        authority_class="accepted_adr_or_active_standard",
        authority_basis="adr_status",
        tracked=True,
        git_blob="fixture-blob",
        content_hash="sha256:fixture-content",
        text=text,
        decode_error=None,
    )


def test_adr_segments_keep_roles_metadata_and_exact_evidence() -> None:
    result = segment_markdown(fixture_source())
    decision = next(
        item for item in result.segments
        if item["segment_kind"] == "paragraph"
        and item["metadata"]["section_role"] == "decision"
    )
    assert decision["text"] == "Checkout must publish OrderPlaced events in production."
    assert decision["heading_path"] == ["Publish order events", "Decision"]
    assert decision["metadata"]["adr_id"] == "ADR-001"
    assert decision["metadata"]["adr_status"] == "accepted"
    evidence = next(item for item in result.evidence if item["segment_id"] == decision["id"])
    assert evidence["text"] == decision["text"]
    assert evidence["span"]["start_line"] == 14

    status = next(
        item
        for item in result.segments
        if item["segment_kind"] == "metadata_field"
        and item["metadata"]["metadata_key"] == "status"
    )
    assert status["text"] == "status: accepted"
    status_evidence = next(
        item for item in result.evidence if item["segment_id"] == status["id"]
    )
    assert status_evidence["span"]["start_line"] == 3


def test_embedded_mermaid_is_statement_bounded() -> None:
    result = segment_markdown(fixture_source())
    statements = [
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    ]
    assert [item["text"] for item in statements] == [
        "Checkout --> Orders : publishes OrderPlaced"
    ]
    assert statements[0]["metadata"]["diagram_language"] == "mermaid"


def test_all_generated_records_have_deterministic_derivations() -> None:
    result = segment_markdown(fixture_source())
    derivation_ids = {item["id"] for item in result.derivations}
    assert derivation_ids
    assert all(set(item["derivation_ids"]) <= derivation_ids for item in result.segments)
    assert all(item["created_at"] is None for item in result.derivations)
    assert all(validate_record_shape(item) is None for item in result.derivations)
