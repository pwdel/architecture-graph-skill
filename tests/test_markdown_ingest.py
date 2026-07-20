from pathlib import Path

from architecture_graph.ingest import IngestionContext
from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.records import validate_record_shape
from architecture_graph.sources import SourceInput


FIXTURE = Path(__file__).parent / "fixtures" / "phase1_repo" / "docs" / "adr" / "ADR-001-events.md"
CONTEXT = IngestionContext(
    configuration_digest="sha256:" + ("a" * 64),
    pipeline_digest="sha256:" + ("b" * 64),
    tool_version="0.1.0",
)


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
    result = segment_markdown(fixture_source(), CONTEXT)
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
    result = segment_markdown(fixture_source(), CONTEXT)
    statements = [
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    ]
    assert [item["text"] for item in statements] == [
        "Checkout --> Orders : publishes OrderPlaced"
    ]
    assert statements[0]["metadata"]["diagram_language"] == "mermaid"


def test_all_generated_records_have_deterministic_derivations() -> None:
    result = segment_markdown(fixture_source(), CONTEXT)
    derivation_ids = {item["id"] for item in result.derivations}
    assert derivation_ids
    assert all(set(item["derivation_ids"]) <= derivation_ids for item in result.segments)
    assert all(item["created_at"] is None for item in result.derivations)
    assert all(validate_record_shape(item) is None for item in result.derivations)


def test_multiline_segment_normalizes_text_but_preserves_evidence() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": "# Decision\n\nCheckout must publish\nOrderPlaced events.\n",
            "content_hash": "sha256:multiline",
        }
    )
    result = segment_markdown(source, CONTEXT)
    segment = next(item for item in result.segments if item["segment_kind"] == "paragraph")
    evidence = next(item for item in result.evidence if item["segment_id"] == segment["id"])
    assert segment["text"] == "Checkout must publish OrderPlaced events."
    assert evidence["text"] == "Checkout must publish\nOrderPlaced events."


def test_malformed_front_matter_warns_but_keeps_recoverable_body() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": "---\nstatus: [accepted\n---\n# Decision\n\nCheckout must publish events.\n",
            "content_hash": "sha256:malformed-frontmatter",
        }
    )
    result = segment_markdown(source, CONTEXT)
    assert [item["code"] for item in result.warnings] == ["unsupported_construct"]
    assert any("Checkout must publish events." == item["text"] for item in result.segments)


def test_embedded_diagram_records_both_structure_and_diagram_derivation() -> None:
    result = segment_markdown(fixture_source(), CONTEXT)
    statement = next(
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    )
    methods = {item["id"]: item["method"] for item in result.derivations}
    assert {methods[item] for item in statement["derivation_ids"]} == {
        "markdown_segmenter",
        "mermaid_segmenter",
    }
    assert all(
        item["configuration_digest"] == CONTEXT.configuration_digest
        for item in result.derivations
    )


def test_longer_fence_token_does_not_close_a_shorter_fence() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": "# Decision\n\n```mermaid\nA --> B\n````python\nB --> C\n```\n",
            "content_hash": "sha256:fence",
        }
    )
    result = segment_markdown(source, CONTEXT)
    assert [
        item["text"]
        for item in result.segments
        if item["segment_kind"] == "diagram_statement"
    ] == ["A --> B", "B --> C"]


def test_commonmark_fence_lengths_indentation_and_unsupported_languages() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": (
                "# Decision\n\n"
                "````mermaid\nA --> B\n`````\n"
                "    ```mermaid\nC --> D\n    ```\n"
                "```python\nprint('not architecture')\n```\n"
            ),
            "content_hash": "sha256:commonmark-fences",
        }
    )
    result = segment_markdown(source, CONTEXT)
    statements = [
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    ]
    assert [item["text"] for item in statements] == ["A --> B"]
    assert any(
        item["code"] == "unsupported_construct" and "python" in item["message"]
        for item in result.warnings
    )


def test_headings_are_first_class_segments_with_exact_evidence() -> None:
    result = segment_markdown(fixture_source(), CONTEXT)
    decision = next(
        item
        for item in result.segments
        if item["segment_kind"] == "heading" and item["text"] == "Decision"
    )
    evidence = next(
        item for item in result.evidence if item["segment_id"] == decision["id"]
    )
    assert decision["heading_path"] == ["Publish order events", "Decision"]
    assert decision["metadata"]["section_role"] == "decision"
    assert evidence["text"] == "## Decision"
    assert evidence["span"]["start_line"] == 12


def test_duplicate_front_matter_key_warns_and_recovers_body() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": (
                "---\n"
                "status: proposed\n"
                "status: accepted\n"
                "---\n"
                "# Decision\n\n"
                "Checkout must publish events.\n"
            ),
            "content_hash": "sha256:duplicate-frontmatter",
        }
    )
    result = segment_markdown(source, CONTEXT)
    assert [item["code"] for item in result.warnings] == ["unsupported_construct"]
    assert "duplicate mapping key: status" in result.warnings[0]["message"]
    assert not any(item["segment_kind"] == "metadata_field" for item in result.segments)
    assert any(item["text"] == "Checkout must publish events." for item in result.segments)


def test_markdown_paragraphs_respect_the_configured_character_bound() -> None:
    bounded_context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": "# Decision\n\n" + ("A" * 300) + "\n",
            "content_hash": "sha256:bounded-markdown",
        }
    )
    result = segment_markdown(source, bounded_context)
    paragraphs = [
        item for item in result.segments if item["segment_kind"] == "paragraph"
    ]
    assert [len(item["text"]) for item in paragraphs] == [256, 44]
    assert [item["span"] for item in paragraphs] == [
        {"start_line": 3, "end_line": 3, "start_column": 1, "end_column": 257},
        {"start_line": 3, "end_line": 3, "start_column": 257, "end_column": 301},
    ]
    evidence_by_segment = {item["segment_id"]: item for item in result.evidence}
    assert all(
        evidence_by_segment[item["id"]]["text"] == item["text"]
        for item in paragraphs
    )


def test_markdown_multiline_evidence_preserves_crlf_bytes() -> None:
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": "# Context\r\n\r\nCheckout owns orders.\r\nWorkers read them.\r\n",
            "content_hash": "sha256:crlf-markdown",
        }
    )
    result = segment_markdown(source, CONTEXT)
    paragraph = next(
        item for item in result.segments if item["segment_kind"] == "paragraph"
    )
    evidence = next(
        item for item in result.evidence if item["segment_id"] == paragraph["id"]
    )
    assert evidence["text"] == "Checkout owns orders.\r\nWorkers read them."


def test_oversized_diagram_and_front_matter_fields_are_visible_and_skipped() -> None:
    bounded_context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )
    source = fixture_source()
    source = SourceInput(
        **{
            **source.__dict__,
            "text": (
                "---\ntitle: " + ("A" * 300) + "\n---\n"
                "# Decision\n\n```mermaid\nCheckout --> "
                + ("B" * 300)
                + "\n```\n"
            ),
            "content_hash": "sha256:oversized-fields",
        }
    )
    result = segment_markdown(source, bounded_context)
    assert [item["segment_kind"] for item in result.segments] == ["heading"]
    assert [item["code"] for item in result.warnings] == [
        "segment_too_large",
        "segment_too_large",
    ]
    derivations = {item["id"] for item in result.derivations}
    assert all(set(item["derivation_ids"]) <= derivations for item in result.warnings)
