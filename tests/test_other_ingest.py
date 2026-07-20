import hashlib
from pathlib import Path

import pytest

from architecture_graph.ingest import IngestionContext, ingest_source, ingest_sources
from architecture_graph.ingest.diagrams import exact_source_excerpt, segment_diagram
from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.ingest.plaintext import segment_plaintext
from architecture_graph.ingest.structured import segment_structured
from architecture_graph.records import SourceSpan, validate_record_shape
from architecture_graph.sources import SourceInput, source_record_id


FIXTURES = Path(__file__).parent / "fixtures" / "phase1_repo"
CONTEXT = IngestionContext(
    "sha256:" + ("a" * 64),
    "sha256:" + ("b" * 64),
    "0.1.0",
)


def source(relative_path: str, source_kind: str, text: str | None = None) -> SourceInput:
    path = FIXTURES / relative_path
    content = path.read_text(encoding="utf-8") if text is None else text
    return SourceInput(
        relative_path=relative_path,
        absolute_path=path,
        source_kind=source_kind,
        document_role="architecture",
        authority_class="maintained_architecture",
        authority_basis="default",
        tracked=True,
        git_blob="fixture-blob",
        content_hash=f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        text=content,
        decode_error=None,
    )


def test_standalone_plantuml_emits_only_directional_statements() -> None:
    result = segment_diagram(
        source("architecture/deployment.puml", "plantuml"), CONTEXT, "plantuml"
    )
    assert [item["text"] for item in result.segments] == [
        "Checkout -> Orders : writes orders",
        "Orders --> Warehouse : publishes OrderPlaced",
    ]
    assert all(
        item["metadata"]["diagram_language"] == "plantuml"
        for item in result.segments
    )
    assert len(result.derivations) == 1


def test_fenced_plantuml_inherits_markdown_section() -> None:
    markdown = source(
        "docs/architecture/embedded.md",
        "markdown",
        "# Runtime\n\n## Decision\n\n```plantuml\nAPI -> Queue : publishes Job\n```\n",
    )
    result = segment_markdown(markdown, CONTEXT)
    statement = next(
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    )
    assert statement["heading_path"] == ["Runtime", "Decision"]
    assert statement["metadata"] == {
        "diagram_language": "plantuml",
        "content_role": "diagram",
        "section_role": "decision",
    }


PLANTUML_WITH_IGNORED_ARROWS = """\
@startuml
/' same-line comment -> Fake '/
/'
multiline comment -> Fake
'/
!define FAKE A -> B
  !include fake -> target
Checkout -> Orders : writes orders /' trailing comment -> Fake '/
@enduml
"""


@pytest.mark.parametrize(
    "relative_path", ["architecture/comments.puml", "architecture/comments.plantuml"]
)
def test_standalone_plantuml_ignores_comments_and_directives(
    relative_path: str,
) -> None:
    result = segment_diagram(
        source(relative_path, "plantuml", PLANTUML_WITH_IGNORED_ARROWS), CONTEXT
    )

    assert [item["text"] for item in result.segments] == [
        "Checkout -> Orders : writes orders"
    ]
    assert [item["text"] for item in result.evidence] == [
        "Checkout -> Orders : writes orders"
    ]


@pytest.mark.parametrize("language", ["plantuml", "puml"])
def test_fenced_plantuml_ignores_comments_and_directives(language: str) -> None:
    result = segment_markdown(
        source(
            "docs/architecture/comments.md",
            "markdown",
            f"# Runtime\n\n```{language}\n{PLANTUML_WITH_IGNORED_ARROWS}```\n",
        ),
        CONTEXT,
    )

    statements = [
        item
        for item in result.segments
        if item["segment_kind"] == "diagram_statement"
    ]
    assert [item["text"] for item in statements] == [
        "Checkout -> Orders : writes orders"
    ]
    statement_evidence = next(
        item for item in result.evidence if item["segment_id"] == statements[0]["id"]
    )
    assert statement_evidence["text"] == "Checkout -> Orders : writes orders"


def test_yaml_and_json_emit_pointer_addressed_scalar_segments() -> None:
    yaml_source = source("architecture/services.yaml", "yaml")
    json_source = source("architecture/interfaces.json", "json")
    yaml_result = segment_structured(yaml_source, CONTEXT)
    json_result = segment_structured(json_source, CONTEXT)
    assert {
        item["metadata"]["json_pointer"]: item["metadata"]["scalar_value"]
        for item in yaml_result.segments
    } == {
        "/services/checkout/database": "orders",
        "/services/checkout/owner": "commerce",
    }
    assert next(iter(json_result.segments))["metadata"]["json_pointer"].startswith(
        "/events/OrderPlaced/"
    )
    for item_source, result in (
        (yaml_source, yaml_result),
        (json_source, json_result),
    ):
        derivation_ids = {item["id"] for item in result.derivations}
        evidence_by_id = {item["id"]: item for item in result.evidence}
        for record in (*result.segments, *result.evidence, *result.derivations):
            validate_record_shape(record)
        for segment in result.segments:
            assert len(segment["evidence_ids"]) == 1
            assert set(segment["derivation_ids"]) <= derivation_ids
            evidence = evidence_by_id[segment["evidence_ids"][0]]
            assert evidence["segment_id"] == segment["id"]
            assert evidence["derivation_ids"] == segment["derivation_ids"]
            assert evidence["text"] == exact_source_excerpt(
                item_source, SourceSpan(**evidence["span"])
            )


def test_duplicate_or_malformed_structured_input_is_a_visible_warning() -> None:
    duplicate = source(
        "architecture/duplicate.yaml",
        "yaml",
        "service: checkout\nservice: orders\n",
    )
    result = segment_structured(duplicate, CONTEXT)
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "duplicate mapping key" in result.warnings[0]["message"]
    validate_record_shape(result.warnings[0])
    assert result.warnings[0]["source_version_id"] == (
        result.derivations[0]["input_ids"][0]
    )
    assert result.warnings[0]["derivation_ids"] == [result.derivations[0]["id"]]


def test_duplicate_json_key_rejects_the_whole_source() -> None:
    result = segment_structured(
        source(
            "architecture/duplicate.json",
            "json",
            '{"service":"checkout","service":"orders"}',
        ),
        CONTEXT,
    )
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "duplicate mapping key" in result.warnings[0]["message"]
    assert result.warnings[0]["derivation_ids"] == [result.derivations[0]["id"]]


def test_duplicate_unpaired_surrogate_json_key_has_a_safe_warning() -> None:
    result = segment_structured(
        source(
            "architecture/duplicate-surrogate.json",
            "json",
            '{"\\ud800":1,"\\ud800":2}',
        ),
        CONTEXT,
    )
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "\\ud800" in result.warnings[0]["message"]
    result.warnings[0]["message"].encode("utf-8")


def test_structured_scalar_failure_does_not_drop_valid_siblings() -> None:
    result = segment_structured(
        source(
            "architecture/isolated-scalar-failure.yaml",
            "yaml",
            "good: 7\nbad: !!int nope\nlater: commerce\n",
        ),
        CONTEXT,
    )
    assert {
        item["metadata"]["json_pointer"]: item["metadata"]["scalar_value"]
        for item in result.segments
    } == {"/good": 7, "/later": "commerce"}
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "/bad" in result.warnings[0]["message"]


def test_yaml_non_finite_scalars_are_rejected_independently() -> None:
    result = segment_structured(
        source(
            "architecture/non-finite.yaml",
            "yaml",
            "finite: 1.5\nnan: .nan\ninfinity: .inf\n",
        ),
        CONTEXT,
    )
    assert [item["metadata"]["json_pointer"] for item in result.segments] == [
        "/finite"
    ]
    assert len(result.warnings) == 2
    assert all("non-finite" in item["message"] for item in result.warnings)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "1e999"])
def test_json_non_finite_numbers_reject_the_source(token: str) -> None:
    result = segment_structured(
        source(
            "architecture/non-finite.json",
            "json",
            '{"valid":1,"invalid":' + token + "}",
        ),
        CONTEXT,
    )
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "non-finite JSON number" in result.warnings[0]["message"]


def test_json_uses_json_scalar_semantics_with_yaml_only_for_spans() -> None:
    result = segment_structured(
        source(
            "architecture/scalars.json",
            "json",
            '{"exponent":1e2,"integer":7,"flag":true,"empty":null}',
        ),
        CONTEXT,
    )
    values = {
        item["metadata"]["json_pointer"]: (
            item["metadata"]["scalar_type"],
            item["metadata"]["scalar_value"],
        )
        for item in result.segments
    }
    assert values == {
        "/empty": ("null", None),
        "/exponent": ("float", 100.0),
        "/flag": ("bool", True),
        "/integer": ("int", 7),
    }


def test_json_escaped_non_bmp_keys_and_values_keep_json_semantics_and_spans() -> None:
    item_source = source(
        "architecture/non-bmp.json",
        "json",
        '{"\\ud83d\\ude00":"ok","emoji":"\\ud83d\\ude00","good":1}',
    )
    result = segment_structured(item_source, CONTEXT)
    values = {
        item["metadata"]["json_pointer"]: item["metadata"]["scalar_value"]
        for item in result.segments
    }
    assert values == {"/emoji": "😀", "/good": 1, "/😀": "ok"}
    evidence_by_id = {item["id"]: item for item in result.evidence}
    for segment in result.segments:
        evidence = evidence_by_id[segment["evidence_ids"][0]]
        assert evidence["text"] == exact_source_excerpt(
            item_source, SourceSpan(**evidence["span"])
        )
    emoji_value = next(
        item
        for item in result.segments
        if item["metadata"]["json_pointer"] == "/emoji"
    )
    assert evidence_by_id[emoji_value["evidence_ids"][0]]["text"] == (
        '"\\ud83d\\ude00"'
    )


def test_unpaired_surrogate_json_key_isolated_with_safe_warning() -> None:
    result = segment_structured(
        source(
            "architecture/surrogate-key.json",
            "json",
            '{"\\ud800":"bad","good":"ok"}',
        ),
        CONTEXT,
    )
    assert {
        item["metadata"]["json_pointer"]: item["metadata"]["scalar_value"]
        for item in result.segments
    } == {"/good": "ok"}
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    warning = result.warnings[0]
    assert "\\ud800" in warning["message"]
    warning["message"].encode("utf-8")
    validate_record_shape(warning)
    assert warning["derivation_ids"] == [result.derivations[0]["id"]]


def test_recursive_yaml_alias_is_rejected_without_recursing() -> None:
    result = segment_structured(
        source(
            "architecture/cycle.yaml",
            "yaml",
            "root: &loop\n  self: *loop\n",
        ),
        CONTEXT,
    )
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "cyclic YAML alias at /root/self" in result.warnings[0]["message"]


def test_deep_structured_input_becomes_a_source_warning() -> None:
    result = segment_structured(
        source(
            "architecture/deep.yaml",
            "yaml",
            ("- " * 1_200) + "leaf\n",
        ),
        CONTEXT,
    )
    assert result.segments == ()
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "recursion" in result.warnings[0]["message"].casefold()
    assert result.warnings[0]["derivation_ids"] == [result.derivations[0]["id"]]


def test_unencodable_json_leaf_does_not_drop_valid_siblings() -> None:
    result = segment_structured(
        source(
            "architecture/surrogate.json",
            "json",
            '{"bad":"\\ud800","good":"ok"}',
        ),
        CONTEXT,
    )
    assert {
        item["metadata"]["json_pointer"]: item["metadata"]["scalar_value"]
        for item in result.segments
    } == {"/good": "ok"}
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert "/bad" in result.warnings[0]["message"]
    result.warnings[0]["message"].encode("utf-8")
    assert result.warnings[0]["derivation_ids"] == [result.derivations[0]["id"]]


@pytest.mark.parametrize(
    ("text", "warning_code", "pointer"),
    [
        ("good: yes\nempty:\n", "parse_failed", "/empty"),
        (
            "defaults: &defaults\n  owner: commerce\ngood: yes\n<<: *defaults\n",
            "unsupported_construct",
            "/<<",
        ),
        ("good: yes\n7: seven\n", "unsupported_construct", "/7"),
    ],
)
def test_unsupported_yaml_constructs_fail_closed_per_leaf_or_entry(
    text: str, warning_code: str, pointer: str
) -> None:
    result = segment_structured(
        source("architecture/unsupported.yaml", "yaml", text), CONTEXT
    )
    assert any(
        item["metadata"]["json_pointer"] == "/good" for item in result.segments
    )
    assert pointer not in {
        item["metadata"]["json_pointer"] for item in result.segments
    }
    assert warning_code in [item["code"] for item in result.warnings]
    warning = next(item for item in result.warnings if item["code"] == warning_code)
    validate_record_shape(warning)
    assert warning["derivation_ids"] == [result.derivations[0]["id"]]


def test_shared_yaml_anchor_keeps_distinct_segment_evidence_links() -> None:
    result = segment_structured(
        source(
            "architecture/shared.yaml",
            "yaml",
            "owner: &owner commerce\nprimary: *owner\nbackup: *owner\n",
        ),
        CONTEXT,
    )
    aliased = [
        item
        for item in result.segments
        if item["metadata"]["json_pointer"] in {"/primary", "/backup"}
    ]
    assert len(aliased) == 2
    evidence = {item["segment_id"]: item for item in result.evidence}
    assert len({evidence[item["id"]]["id"] for item in aliased}) == 2
    assert {evidence[item["id"]]["text"] for item in aliased} == {"commerce"}


def test_multiline_scalar_evidence_is_the_exact_source_slice() -> None:
    result = segment_structured(
        source(
            "architecture/multiline.yaml",
            "yaml",
            'summary: "Checkout owns\n  orders"\nowner: commerce\n',
        ),
        CONTEXT,
    )
    summary = next(
        item
        for item in result.segments
        if item["metadata"]["json_pointer"] == "/summary"
    )
    item_evidence = next(
        item for item in result.evidence if item["segment_id"] == summary["id"]
    )
    assert item_evidence["text"] == '"Checkout owns\n  orders"'


def test_structured_multiline_evidence_preserves_crlf_bytes() -> None:
    item_source = source(
        "architecture/crlf.yaml",
        "yaml",
        'summary: "Checkout owns\r\n  orders"\r\nowner: commerce\r\n',
    )
    result = segment_structured(item_source, CONTEXT)
    summary = next(
        item
        for item in result.segments
        if item["metadata"]["json_pointer"] == "/summary"
    )
    item_evidence = next(
        item for item in result.evidence if item["segment_id"] == summary["id"]
    )
    assert item_evidence["text"] == '"Checkout owns\r\n  orders"'
    assert item_evidence["text"] == exact_source_excerpt(
        item_source, SourceSpan(**item_evidence["span"])
    )


def test_oversized_structured_scalar_is_visible_and_skipped() -> None:
    bounded_context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )
    result = segment_structured(
        source(
            "architecture/large.yaml",
            "yaml",
            "large: " + ("A" * 300) + "\nsmall: orders\n",
        ),
        bounded_context,
    )
    assert [item["metadata"]["json_pointer"] for item in result.segments] == [
        "/small"
    ]
    assert [item["code"] for item in result.warnings] == ["segment_too_large"]


def test_plain_text_uses_paragraph_boundaries() -> None:
    item_source = source("architecture/notes.txt", "text")
    result = segment_plaintext(item_source, CONTEXT)
    assert [item["text"] for item in result.segments] == [
        "Checkout owns the order lifecycle. It publishes OrderPlaced after payment authorization.",
        "Warehouse consumes OrderPlaced idempotently.",
    ]
    assert [item["span"] for item in result.segments] == [
        {"start_line": 1, "end_line": 2, "start_column": 1, "end_column": 54},
        {"start_line": 4, "end_line": 4, "start_column": 1, "end_column": 45},
    ]
    evidence_by_id = {item["id"]: item for item in result.evidence}
    for segment in result.segments:
        validate_record_shape(segment)
        evidence = evidence_by_id[segment["evidence_ids"][0]]
        validate_record_shape(evidence)
        assert evidence["text"] == exact_source_excerpt(
            item_source, SourceSpan(**segment["span"])
        )


def test_plain_text_splits_oversized_paragraphs_with_exact_evidence() -> None:
    bounded_context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )
    result = segment_plaintext(
        source("architecture/long.txt", "text", "A" * 300 + "\n"),
        bounded_context,
    )
    assert [len(item["text"]) for item in result.segments] == [256, 44]
    assert [item["span"] for item in result.segments] == [
        {"start_line": 1, "end_line": 1, "start_column": 1, "end_column": 257},
        {"start_line": 1, "end_line": 1, "start_column": 257, "end_column": 301},
    ]
    evidence_by_id = {item["id"]: item for item in result.evidence}
    assert all(
        evidence_by_id[item["evidence_ids"][0]]["text"] == item["text"]
        for item in result.segments
    )


def test_plain_text_formatting_alone_cannot_create_oversized_evidence() -> None:
    bounded_context = IngestionContext(
        configuration_digest=CONTEXT.configuration_digest,
        pipeline_digest=CONTEXT.pipeline_digest,
        tool_version=CONTEXT.tool_version,
        max_segment_chars=256,
    )
    item_source = source(
        "architecture/formatted.txt",
        "text",
        (" " * 300) + "alpha" + (" " * 300) + "omega\n",
    )
    result = segment_plaintext(item_source, bounded_context)
    evidence_by_id = {item["id"]: item for item in result.evidence}
    assert result.segments
    assert all(item["text"].strip() for item in result.segments)
    for segment in result.segments:
        evidence = evidence_by_id[segment["evidence_ids"][0]]
        assert len(segment["text"]) <= bounded_context.max_segment_chars
        assert len(evidence["text"]) <= bounded_context.max_segment_chars
        assert evidence["text"] == exact_source_excerpt(
            item_source, SourceSpan(**evidence["span"])
        )


def test_plain_text_multiline_evidence_preserves_crlf_bytes() -> None:
    item_source = source(
        "architecture/crlf.txt",
        "text",
        "Checkout owns orders.\r\nWorkers read them.\r\n",
    )
    result = segment_plaintext(item_source, CONTEXT)
    assert result.evidence[0]["text"] == (
        "Checkout owns orders.\r\nWorkers read them."
    )
    assert result.evidence[0]["text"] == exact_source_excerpt(
        item_source, SourceSpan(**result.evidence[0]["span"])
    )


@pytest.mark.parametrize(
    ("kind", "expected_method"),
    [
        ("markdown", "markdown_segmenter"),
        ("mermaid", "mermaid_segmenter"),
        ("plantuml", "plantuml_segmenter"),
        ("yaml", "structured_segmenter"),
        ("json", "structured_segmenter"),
        ("text", "plaintext_segmenter"),
    ],
)
def test_dispatch_is_explicit_and_records_the_adapter(
    kind: str, expected_method: str
) -> None:
    fixtures = {
        "markdown": source(
            "docs/architecture/one.md", "markdown", "# Decision\n\nA must call B.\n"
        ),
        "mermaid": source("architecture/one.mmd", "mermaid", "A --> B\n"),
        "plantuml": source("architecture/one.puml", "plantuml", "A -> B\n"),
        "yaml": source("architecture/one.yaml", "yaml", "service: checkout\n"),
        "json": source("architecture/one.json", "json", '{"service":"checkout"}'),
        "text": source("architecture/one.txt", "text", "A calls B.\n"),
    }
    result = ingest_source(fixtures[kind], CONTEXT)
    assert result.derivations[0]["method"] == expected_method


@pytest.mark.parametrize(
    ("adapter", "wrong_kind"),
    [(segment_structured, "text"), (segment_plaintext, "yaml")],
)
def test_direct_adapters_reject_wrong_source_kinds(adapter, wrong_kind: str) -> None:
    with pytest.raises(ValueError, match="source kind"):
        adapter(
            source(f"architecture/wrong.{wrong_kind}", wrong_kind, "value"),
            CONTEXT,
        )


def test_dispatch_rejects_an_unknown_source_kind() -> None:
    with pytest.raises(ValueError, match="no ingestion adapter"):
        ingest_source(
            source("architecture/unknown.bin", "unsupported", "value"), CONTEXT
        )


def test_ingest_sources_rejects_duplicate_paths_before_dispatch() -> None:
    first = source("architecture/same.txt", "text", "first")
    duplicate = source("architecture/same.txt", "unsupported", "second")
    with pytest.raises(ValueError, match="duplicate source path"):
        ingest_sources((first, duplicate), CONTEXT)


def test_ingest_sources_orders_unique_paths_and_recovers_after_warning() -> None:
    last = source("architecture/c.txt", "text", "last")
    malformed = source("architecture/b.yaml", "yaml", "broken: [\n")
    first = source("architecture/a.txt", "text", "first")
    result = ingest_sources((last, malformed, first), CONTEXT)
    assert [item["text"] for item in result.segments] == ["first", "last"]
    assert [item["path"] for item in result.evidence] == [
        "architecture/a.txt",
        "architecture/c.txt",
    ]
    assert [item["input_ids"][0] for item in result.derivations] == [
        source_record_id(first),
        source_record_id(malformed),
        source_record_id(last),
    ]
    assert [item["code"] for item in result.warnings] == ["parse_failed"]
    assert result.warnings[0]["source_version_id"] == source_record_id(malformed)
