from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.sources import SourceInput


def markdown_source(text: str) -> SourceInput:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceInput(
        relative_path="docs/adr/ADR-regression.md",
        absolute_path=Path("/tmp/ADR-regression.md"),
        source_kind="markdown",
        document_role="adr",
        authority_class="accepted_adr_or_active_standard",
        authority_basis="adr_status",
        tracked=True,
        git_blob="fixture-blob",
        content_hash=f"sha256:{digest}",
        text=text,
        decode_error=None,
    )


@pytest.mark.parametrize(
    ("front_matter", "message_fragment"),
    [
        ("- id: ADR-1", "mapping"),
        ("id: FIRST\nid: SECOND\nstatus: accepted", "duplicate"),
        ("id: FIRST\nｉｄ: SECOND\nstatus: accepted", "normalized"),
        ("1: accepted", "string"),
        ("id: 2026-07-20\nstatus: accepted", "canonical JSON"),
    ],
)
def test_invalid_front_matter_warns_without_emitting_records(
    front_matter: str, message_fragment: str
) -> None:
    result = segment_markdown(
        markdown_source(f"---\n{front_matter}\n---\n# Ignored after invalid metadata\n")
    )

    assert result.segments == ()
    assert result.evidence == ()
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
    assert message_fragment in str(result.warnings[0]["message"])


def test_commonmark_list_markers_emit_one_segment_per_item() -> None:
    result = segment_markdown(
        markdown_source(
            "# Lists\n\n"
            "- dash\n"
            "+ plus\n"
            "* star\n"
            "1. ordered dot\n"
            "2) ordered parenthesis\n"
        )
    )

    items = [
        segment for segment in result.segments if segment["segment_kind"] == "list_item"
    ]
    assert [item["text"] for item in items] == [
        "- dash",
        "+ plus",
        "* star",
        "1. ordered dot",
        "2) ordered parenthesis",
    ]
    assert [item["span"]["start_line"] for item in items] == [3, 4, 5, 6, 7]


def test_list_markers_require_following_whitespace() -> None:
    result = segment_markdown(
        markdown_source("-not\n+not\n*not\n1.not\n2)not\n")
    )

    assert not any(
        segment["segment_kind"] == "list_item" for segment in result.segments
    )


def test_evidence_preserves_exact_source_slices_and_exclusive_columns() -> None:
    result = segment_markdown(
        markdown_source(
            "---\r\n"
            "id: ADR-CRLF\r\n"
            "status: accepted\r\n"
            "---\r\n"
            "\r\n"
            "# Heading  \r\n"
            "\r\n"
            "line one\r\n"
            "  line two\r\n"
            "\r\n"
            "```mermaid\r\n"
            "   A --> B   \r\n"
            "```\r\n"
        )
    )

    evidence_by_segment = {
        evidence["segment_id"]: evidence for evidence in result.evidence
    }
    status = next(
        segment
        for segment in result.segments
        if segment["segment_kind"] == "metadata_field"
        and segment["metadata"]["metadata_key"] == "status"
    )
    heading = next(
        segment for segment in result.segments if segment["segment_kind"] == "heading"
    )
    paragraph = next(
        segment for segment in result.segments if segment["segment_kind"] == "paragraph"
    )
    diagram = next(
        segment
        for segment in result.segments
        if segment["segment_kind"] == "diagram_statement"
    )

    assert status["text"] == "status: accepted"
    assert evidence_by_segment[status["id"]]["text"] == "status: accepted"
    assert status["span"] == {
        "start_line": 3,
        "end_line": 3,
        "start_column": 1,
        "end_column": 17,
    }

    assert heading["text"] == "Heading"
    assert evidence_by_segment[heading["id"]]["text"] == "# Heading  "
    assert heading["span"]["end_column"] == 12

    assert paragraph["text"] == "line one line two"
    assert evidence_by_segment[paragraph["id"]]["text"] == "line one\r\n  line two"
    assert paragraph["span"] == {
        "start_line": 8,
        "end_line": 9,
        "start_column": 1,
        "end_column": 11,
    }

    assert diagram["text"] == "A --> B"
    assert evidence_by_segment[diagram["id"]]["text"] == "A --> B"
    assert diagram["span"] == {
        "start_line": 12,
        "end_line": 12,
        "start_column": 4,
        "end_column": 11,
    }


def test_mermaid_compound_line_splits_into_exact_statement_spans() -> None:
    result = segment_markdown(
        markdown_source(
            "# Diagram\n\n```mermaid\n  A --> B; B --> C  \n```\n"
        )
    )

    statements = [
        segment
        for segment in result.segments
        if segment["segment_kind"] == "diagram_statement"
    ]
    evidence_by_segment = {
        evidence["segment_id"]: evidence for evidence in result.evidence
    }
    assert [statement["text"] for statement in statements] == [
        "A --> B",
        "B --> C",
    ]
    assert [statement["span"] for statement in statements] == [
        {
            "start_line": 4,
            "end_line": 4,
            "start_column": 3,
            "end_column": 10,
        },
        {
            "start_line": 4,
            "end_line": 4,
            "start_column": 12,
            "end_column": 19,
        },
    ]
    assert [evidence_by_segment[item["id"]]["text"] for item in statements] == [
        "A --> B",
        "B --> C",
    ]


def test_unsplittable_mermaid_compound_fails_closed_with_warning() -> None:
    result = segment_markdown(
        markdown_source(
            "# Diagram\n\n```mermaid\nA --> B B --> C\n```\n"
        )
    )

    assert not any(
        segment["segment_kind"] == "diagram_statement"
        for segment in result.segments
    )
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
