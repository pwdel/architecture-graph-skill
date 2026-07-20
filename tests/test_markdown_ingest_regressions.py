from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from architecture_graph.ingest import IngestionContext
from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.sources import SourceInput


CONTEXT = IngestionContext(
    configuration_digest="sha256:" + ("a" * 64),
    pipeline_digest="sha256:" + ("b" * 64),
    tool_version="0.1.0",
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("configuration_digest", ""),
        ("configuration_digest", "sha256:short"),
        ("configuration_digest", "SHA256:" + ("a" * 64)),
        ("configuration_digest", "sha256:" + ("A" * 64)),
        ("pipeline_digest", ""),
        ("pipeline_digest", "sha256:short"),
        ("pipeline_digest", "SHA256:" + ("b" * 64)),
        ("pipeline_digest", "sha256:" + ("B" * 64)),
    ],
)
def test_ingestion_context_rejects_invalid_digests(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "configuration_digest": CONTEXT.configuration_digest,
        "pipeline_digest": CONTEXT.pipeline_digest,
        "tool_version": CONTEXT.tool_version,
    }
    values[field] = value

    with pytest.raises(ValueError):
        IngestionContext(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("tool_version", [None, 1, "", " ", "\t\n"])
def test_ingestion_context_rejects_invalid_tool_versions(
    tool_version: object,
) -> None:
    with pytest.raises(ValueError):
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=tool_version,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("max_segment_chars", [True, False, 0, -1, -256, 255])
def test_ingestion_context_rejects_invalid_segment_bounds(
    max_segment_chars: object,
) -> None:
    with pytest.raises(ValueError):
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=max_segment_chars,  # type: ignore[arg-type]
        )


def test_ingestion_context_accepts_the_exact_minimum_segment_bound() -> None:
    context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )

    assert context.max_segment_chars == 256


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
def test_invalid_front_matter_warns_and_recovers_body_without_metadata(
    front_matter: str, message_fragment: str
) -> None:
    result = segment_markdown(
        markdown_source(f"---\n{front_matter}\n---\n# Recovered after invalid metadata\n"),
        CONTEXT,
    )

    assert [
        segment["text"]
        for segment in result.segments
        if segment["segment_kind"] == "heading"
    ] == ["Recovered after invalid metadata"]
    assert not any(
        segment["segment_kind"] == "metadata_field"
        for segment in result.segments
    )
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
    assert message_fragment in str(result.warnings[0]["message"])


def test_recursive_yaml_alias_warns_and_recovers_body_without_metadata() -> None:
    result = segment_markdown(
        markdown_source(
            "---\n"
            "id: &loop [*loop]\n"
            "status: accepted\n"
            "---\n"
            "# Recovered after recursive metadata\n"
        ),
        CONTEXT,
    )

    assert [segment["text"] for segment in result.segments] == [
        "Recovered after recursive metadata"
    ]
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
    assert "recursive" in str(result.warnings[0]["message"])


def test_shared_acyclic_yaml_alias_warns_and_recovers_body_without_metadata() -> None:
    source = markdown_source(
        "---\n"
        "defaults: &base {region: us}\n"
        "a: *base\n"
        "b: *base\n"
        "id: ADR-ALIASES\n"
        "status: accepted\n"
        "---\n"
        "# Recovered after aliased metadata\n"
    )

    first = segment_markdown(source, CONTEXT)
    second = segment_markdown(source, CONTEXT)

    assert [segment["text"] for segment in first.segments] == [
        "Recovered after aliased metadata"
    ]
    assert [warning["code"] for warning in first.warnings] == [
        "unsupported_construct"
    ]
    assert "alias" in str(first.warnings[0]["message"])
    assert second.warnings[0]["id"] == first.warnings[0]["id"]


def test_nested_yaml_without_aliases_remains_supported() -> None:
    result = segment_markdown(
        markdown_source(
            "---\n"
            "id: ADR-NESTED\n"
            "status: accepted\n"
            "defaults:\n"
            "  region: us\n"
            "  zones:\n"
            "    - central\n"
            "---\n"
            "# Nested metadata\n"
        ),
        CONTEXT,
    )

    assert result.warnings == ()
    assert [
        segment["metadata"]["metadata_key"]
        for segment in result.segments
        if segment["segment_kind"] == "metadata_field"
    ] == ["id", "status"]


def test_commonmark_list_markers_emit_one_segment_per_item() -> None:
    result = segment_markdown(
        markdown_source(
            "# Lists\n\n"
            "- dash\n"
            "+ plus\n"
            "* star\n"
            "1. ordered dot\n"
            "2) ordered parenthesis\n"
        ),
        CONTEXT,
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
        markdown_source("-not\n+not\n*not\n1.not\n2)not\n"),
        CONTEXT,
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
        ),
        CONTEXT,
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
        ),
        CONTEXT,
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
    source = markdown_source(
        "# Diagram\n\n```mermaid\nA --> B B --> C\n```\n"
    )
    result = segment_markdown(source, CONTEXT)
    repeated = segment_markdown(source, CONTEXT)

    assert not any(
        segment["segment_kind"] == "diagram_statement"
        for segment in result.segments
    )
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
    assert result.warnings[0]["message"] == (
        "unsplittable compound Mermaid statement"
    )
    assert result.warnings[0]["id"] == repeated.warnings[0]["id"]
    assert (
        result.warnings[0]["content_digest"]
        == repeated.warnings[0]["content_digest"]
    )


def test_unclosed_front_matter_returns_only_warning_and_derivation() -> None:
    result = segment_markdown(
        markdown_source(
            "---\n"
            "id: ADR-UNCLOSED\n"
            "status: accepted\n"
            "# Must not be recovered without a closing delimiter\n"
        ),
        CONTEXT,
    )

    assert result.segments == ()
    assert result.evidence == ()
    assert len(result.derivations) == 1
    assert [warning["code"] for warning in result.warnings] == [
        "unsupported_construct"
    ]
    assert "closing delimiter not found" in str(result.warnings[0]["message"])


def test_nested_heading_path_at_exact_bound_keeps_full_path_and_role() -> None:
    ancestor = "A" * 248
    result = segment_markdown(
        markdown_source(
            f"# {ancestor}\n\n"
            "## Decision\n\n"
            "Publish events.\n\n"
            "```mermaid\nCheckout --> Orders\n```\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    body = [
        segment
        for segment in result.segments
        if segment["segment_kind"] in {"paragraph", "diagram_statement"}
    ]
    assert result.warnings == ()
    assert [segment["heading_path"] for segment in body] == [
        [ancestor, "Decision"],
        [ancestor, "Decision"],
    ]
    assert [segment["metadata"]["section_role"] for segment in body] == [
        "decision",
        "decision",
    ]


def test_overbound_ancestors_keep_complete_most_specific_heading_suffix() -> None:
    ancestor = "A" * 249
    result = segment_markdown(
        markdown_source(
            f"# {ancestor}\n\n"
            "## Decision\n\n"
            "Publish events.\n\n"
            "```mermaid\nCheckout --> Orders\n```\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    active_heading = next(
        segment
        for segment in result.segments
        if segment["segment_kind"] == "heading"
        and segment["text"] == "Decision"
    )
    body = [
        segment
        for segment in result.segments
        if segment["segment_kind"] in {"paragraph", "diagram_statement"}
    ]
    assert active_heading["heading_path"] == ["Decision"]
    assert active_heading["metadata"]["section_role"] == "decision"
    assert [segment["heading_path"] for segment in body] == [
        ["Decision"],
        ["Decision"],
    ]
    assert [segment["metadata"]["section_role"] for segment in body] == [
        "decision",
        "decision",
    ]
    assert [warning["code"] for warning in result.warnings] == [
        "segment_too_large"
    ]


def test_overbound_active_heading_uses_empty_context_semantics() -> None:
    active = "Decision" + ("A" * 249)
    result = segment_markdown(
        markdown_source(
            f"# {active}\n\n"
            "Publish events.\n\n"
            "```mermaid\nCheckout --> Orders\n```\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    body = [
        segment
        for segment in result.segments
        if segment["segment_kind"] in {"paragraph", "diagram_statement"}
    ]
    assert not any(
        segment["segment_kind"] == "heading" for segment in result.segments
    )
    assert [segment["heading_path"] for segment in body] == [[], []]
    assert [segment["metadata"]["section_role"] for segment in body] == [
        "context",
        "context",
    ]
    assert [warning["code"] for warning in result.warnings] == [
        "segment_too_large"
    ]


def test_oversized_id_is_removed_from_all_remaining_segment_metadata() -> None:
    oversized_id = "I" * 253
    result = segment_markdown(
        markdown_source(
            f"---\nid: {oversized_id}\nstatus: accepted\n---\n"
            "# Decision\n\nPublish events.\n\n"
            "- Keep ordering.\n\n"
            "```mermaid\nCheckout --> Orders\n```\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    assert not any(
        segment["segment_kind"] == "metadata_field"
        and segment["metadata"]["metadata_key"] == "id"
        for segment in result.segments
    )
    assert all(
        segment["metadata"].get("adr_id") is None
        for segment in result.segments
    )
    assert all(
        segment["metadata"].get("adr_status") == "accepted"
        for segment in result.segments
    )
    assert [warning["code"] for warning in result.warnings] == [
        "segment_too_large"
    ]


def test_oversized_status_is_removed_from_all_remaining_segment_metadata() -> None:
    oversized_status = "S" * 249
    result = segment_markdown(
        markdown_source(
            f"---\nid: ADR-BOUNDED\nstatus: {oversized_status}\n---\n"
            "# Decision\n\nPublish events.\n\n"
            "- Keep ordering.\n\n"
            "```mermaid\nCheckout --> Orders\n```\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    assert not any(
        segment["segment_kind"] == "metadata_field"
        and segment["metadata"]["metadata_key"] == "status"
        for segment in result.segments
    )
    assert all(
        segment["metadata"].get("adr_id") == "ADR-BOUNDED"
        for segment in result.segments
    )
    assert all(
        segment["metadata"].get("adr_status") is None
        for segment in result.segments
    )
    assert [warning["code"] for warning in result.warnings] == [
        "segment_too_large"
    ]


def test_supported_metadata_field_at_exact_bound_remains_effective() -> None:
    exact_id = "I" * 252
    result = segment_markdown(
        markdown_source(
            f"---\nid: {exact_id}\nstatus: accepted\n---\n"
            "# Decision\n\nPublish events.\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    id_field = next(
        segment
        for segment in result.segments
        if segment["segment_kind"] == "metadata_field"
        and segment["metadata"]["metadata_key"] == "id"
    )
    assert len(id_field["text"]) == 256
    assert id_field["metadata"]["metadata_value"] == exact_id
    assert all(
        segment["metadata"].get("adr_id") == exact_id
        for segment in result.segments
    )
    assert result.warnings == ()


def test_oversized_multiline_metadata_scalar_is_warning_only() -> None:
    multiline_id = "I" * 248
    result = segment_markdown(
        markdown_source(
            f"---\nid: >-\n  {multiline_id}\nstatus: accepted\n---\n"
            "# Decision\n\nPublish events.\n"
        ),
        IngestionContext(
            configuration_digest=CONTEXT.configuration_digest,
            pipeline_digest=CONTEXT.pipeline_digest,
            tool_version=CONTEXT.tool_version,
            max_segment_chars=256,
        ),
    )

    assert not any(
        segment["segment_kind"] == "metadata_field"
        and segment["metadata"]["metadata_key"] == "id"
        for segment in result.segments
    )
    assert all(
        segment["metadata"].get("adr_id") is None
        for segment in result.segments
    )
    assert [warning["span"] for warning in result.warnings] == [
        {
            "start_line": 2,
            "end_line": 4,
            "start_column": 1,
            "end_column": 1,
        }
    ]
    assert all(
        segment["metadata"].get("adr_status") == "accepted"
        for segment in result.segments
    )
