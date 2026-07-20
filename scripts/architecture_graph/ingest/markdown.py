from __future__ import annotations

from collections.abc import Mapping
import re
import unicodedata

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from architecture_graph.canonical import canonicalize
from architecture_graph.ingest import IngestionContext, IngestionResult
from architecture_graph.ingest.diagrams import (
    derivation_record,
    diagram_statement_records,
    exact_source_excerpt,
    segment_and_evidence,
    warning_record,
)
from architecture_graph.records import Record, SourceSpan
from architecture_graph.sources import SourceInput


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_OPEN = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
LIST_ITEM = re.compile(r"^ {0,3}(?:[-+*]|[0-9]{1,9}[.)])[ \t]+")
YAML_STRING_TAG = "tag:yaml.org,2002:str"
SUPPORTED_METADATA = ("id", "title", "date", "status")
SECTION_ROLES = {
    "context": "context",
    "driver": "rationale",
    "drivers": "rationale",
    "rationale": "rationale",
    "decision": "decision",
    "options": "option",
    "alternatives": "option",
    "consequences": "consequence",
    "tradeoffs": "consequence",
    "risks": "consequence",
    "outcomes": "consequence",
    "status": "status",
}


def _opening_fence(raw: str) -> tuple[str, int, str] | None:
    match = FENCE_OPEN.fullmatch(raw)
    if match is None:
        return None
    marker = match.group("marker")
    info = match.group("info").strip()
    if marker[0] == "`" and "`" in info:
        return None
    language = info.split(maxsplit=1)[0] if info else ""
    return marker[0], len(marker), language


def _is_closing_fence(raw: str, marker: str, opening_length: int) -> bool:
    return re.fullmatch(
        rf" {{0,3}}{re.escape(marker)}{{{opening_length},}}[ \t]*", raw
    ) is not None


class FrontMatterError(ValueError):
    pass


def _validate_yaml_node(
    node: Node,
    visited: set[int] | None = None,
    active: set[int] | None = None,
) -> None:
    visited = set() if visited is None else visited
    active = set() if active is None else active
    identity = id(node)
    if identity in active:
        raise FrontMatterError("recursive YAML alias in front matter")
    if identity in visited:
        raise FrontMatterError("YAML aliases are unsupported in front matter")
    visited.add(identity)
    active.add(identity)
    try:
        if isinstance(node, MappingNode):
            normalized_keys: dict[str, str] = {}
            for key_node, value_node in node.value:
                if (
                    not isinstance(key_node, ScalarNode)
                    or key_node.tag != YAML_STRING_TAG
                ):
                    raise FrontMatterError(
                        "front matter mapping keys must be string scalars"
                    )
                _validate_yaml_node(key_node, visited, active)
                key = key_node.value
                normalized = unicodedata.normalize("NFKC", key)
                if normalized in normalized_keys:
                    previous = normalized_keys[normalized]
                    if previous == key:
                        raise FrontMatterError(f"duplicate mapping key: {key}")
                    raise FrontMatterError(
                        "normalized front matter key collision: "
                        f"{previous!r} and {key!r}"
                    )
                normalized_keys[normalized] = key
                _validate_yaml_node(value_node, visited, active)
        elif isinstance(node, SequenceNode):
            for item in node.value:
                _validate_yaml_node(item, visited, active)
    finally:
        active.remove(identity)


def _reject_recursive_containers(
    value: object, active: set[int] | None = None
) -> None:
    if isinstance(value, Mapping):
        children = value.values()
    elif isinstance(value, (list, tuple)):
        children = value
    else:
        return

    active = set() if active is None else active
    identity = id(value)
    if identity in active:
        raise FrontMatterError("recursive YAML value in front matter")
    active.add(identity)
    try:
        for child in children:
            _reject_recursive_containers(child, active)
    finally:
        active.remove(identity)


def _parse_front_matter(
    raw_metadata: str,
) -> tuple[dict[str, object], dict[str, SourceSpan]]:
    node = yaml.compose(raw_metadata, Loader=yaml.SafeLoader)
    if not isinstance(node, MappingNode):
        raise FrontMatterError("front matter must be a mapping")
    _validate_yaml_node(node)
    loaded = yaml.safe_load(raw_metadata)
    if not isinstance(loaded, dict):
        raise FrontMatterError("front matter must be a mapping")
    _reject_recursive_containers(loaded)
    try:
        canonicalize(loaded)
    except RecursionError as error:
        raise FrontMatterError("recursive YAML value in front matter") from error
    except (TypeError, ValueError) as error:
        raise FrontMatterError(
            f"front matter values must be canonical JSON: {error}"
        ) from error

    metadata: dict[str, object] = {}
    spans: dict[str, SourceSpan] = {}
    for key_node, value_node in node.value:
        key = key_node.value
        if key not in SUPPORTED_METADATA:
            continue
        if not isinstance(value_node, ScalarNode):
            raise FrontMatterError(
                f"front matter field {key} must be a scalar"
            )
        value = loaded[key]
        normalized = "" if value is None else str(value)
        metadata[key] = normalized.casefold() if key == "status" else normalized
        spans[key] = SourceSpan(
            key_node.start_mark.line + 2,
            value_node.end_mark.line + 2,
            key_node.start_mark.column + 1,
            value_node.end_mark.column + 1,
        )
    return metadata, spans


def _bounded_paragraphs(
    paragraph: list[tuple[int, str]], max_chars: int, source: SourceInput
) -> list[tuple[str, str, SourceSpan]]:
    normalized = " ".join(raw.strip() for _, raw in paragraph).strip()
    if len(normalized) <= max_chars:
        span = SourceSpan(
            paragraph[0][0],
            paragraph[-1][0],
            1,
            len(paragraph[-1][1]) + 1,
        )
        return [(normalized, exact_source_excerpt(source, span), span)]

    chunks: list[tuple[str, str, SourceSpan]] = []
    for line_number, raw in paragraph:
        leading = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        for offset in range(0, len(stripped), max_chars):
            text = stripped[offset : offset + max_chars]
            if not text:
                continue
            start_column = leading + offset + 1
            span = SourceSpan(
                line_number,
                line_number,
                start_column,
                start_column + len(text),
            )
            chunks.append((text, exact_source_excerpt(source, span), span))
    return chunks


def segment_markdown(
    source: SourceInput, context: IngestionContext
) -> IngestionResult:
    derivation = derivation_record(source, "markdown_segmenter", context)
    derivation_id = str(derivation["id"])
    if source.decode_error is not None:
        warning = warning_record(
            source,
            code="parse_failed",
            message=source.decode_error,
            span=None,
            possible_role=None,
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))

    lines = source.text.splitlines()
    metadata: dict[str, object] = {}
    metadata_spans: dict[str, SourceSpan] = {}
    warnings: list[Record] = []
    cursor = 0
    if lines and lines[0].strip() == "---":
        closing = next(
            (
                index
                for index in range(1, len(lines))
                if lines[index].strip() == "---"
            ),
            None,
        )
        if closing is None:
            warning = warning_record(
                source,
                code="unsupported_construct",
                message=(
                    "invalid Markdown front matter: closing delimiter not found"
                ),
                span=SourceSpan(1, max(1, len(lines))),
                possible_role="status",
                derivation_ids=(derivation_id,),
            )
            return IngestionResult(
                derivations=(derivation,), warnings=(warning,)
            )
        cursor = closing + 1
        front_lines = source.text.splitlines(keepends=True)[1:closing]
        try:
            metadata, metadata_spans = _parse_front_matter(
                "".join(front_lines)
            )
        except (FrontMatterError, yaml.YAMLError) as error:
            metadata = {}
            metadata_spans = {}
            warnings.append(
                warning_record(
                    source,
                    code="unsupported_construct",
                    message=f"invalid Markdown front matter: {error}",
                    span=SourceSpan(1, closing + 1),
                    possible_role="status",
                    derivation_ids=(derivation_id,),
                )
            )

    heading_levels: list[tuple[int, str]] = []
    segments: list[Record] = []
    evidence: list[Record] = []
    paragraph: list[tuple[int, str]] = []
    diagram_derivations: dict[str, Record] = {}

    for key in SUPPORTED_METADATA:
        if key not in metadata or key not in metadata_spans:
            continue
        span = metadata_spans[key]
        evidence_text = exact_source_excerpt(source, span)
        if len(evidence_text) > context.max_segment_chars:
            warnings.append(
                warning_record(
                    source,
                    code="segment_too_large",
                    message=(
                        f"Markdown front matter field {key} exceeds "
                        "max_segment_chars"
                    ),
                    span=span,
                    possible_role="status" if key == "status" else "context",
                    derivation_ids=(derivation_id,),
                )
            )
            continue
        segment, item_evidence = segment_and_evidence(
            source,
            segment_kind="metadata_field",
            segment_text=evidence_text.strip(),
            evidence_text=evidence_text,
            span=span,
            heading_path=(),
            metadata={
                "section_role": "status" if key == "status" else "context",
                "metadata_key": key,
                "metadata_value": metadata[key],
                "adr_id": metadata.get("id"),
                "adr_status": metadata.get("status"),
            },
            derivation_ids=(derivation_id,),
            ordinal=len(segments),
        )
        segments.append(segment)
        evidence.append(item_evidence)

    def heading_path() -> list[str]:
        remaining = context.max_segment_chars
        bounded: list[str] = []
        for _, title in heading_levels:
            if remaining <= 0:
                break
            selected = title[:remaining]
            if selected:
                bounded.append(selected)
                remaining -= len(selected)
        return bounded

    def section_role() -> str:
        if not heading_levels:
            return "context"
        return SECTION_ROLES.get(heading_levels[-1][1].strip().casefold(), "context")

    def emit_paragraph() -> None:
        if not paragraph:
            return
        segment_kind = (
            "list_item" if LIST_ITEM.match(paragraph[0][1]) else "paragraph"
        )
        for text, evidence_text, span in _bounded_paragraphs(
            paragraph, context.max_segment_chars, source
        ):
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind=segment_kind,
                segment_text=text,
                evidence_text=evidence_text,
                span=span,
                heading_path=heading_path(),
                metadata={
                    "section_role": section_role(),
                    "adr_id": metadata.get("id"),
                    "adr_status": metadata.get("status"),
                },
                derivation_ids=(derivation_id,),
                ordinal=len(segments),
            )
            segments.append(segment)
            evidence.append(item_evidence)
        paragraph.clear()

    while cursor < len(lines):
        raw = lines[cursor]
        line_number = cursor + 1
        opening = _opening_fence(raw)
        if opening is not None:
            emit_paragraph()
            marker, opening_length, language = opening
            enclosing_role = section_role()
            block: list[tuple[int, str]] = []
            cursor += 1
            while cursor < len(lines) and not _is_closing_fence(
                lines[cursor], marker, opening_length
            ):
                block.append((cursor + 1, lines[cursor]))
                cursor += 1
            if cursor == len(lines):
                warnings.append(
                    warning_record(
                        source,
                        code="unsupported_construct",
                        message=f"unclosed {language or 'code'} fence",
                        span=SourceSpan(line_number, len(lines)),
                        possible_role=enclosing_role,
                        derivation_ids=(derivation_id,),
                    )
                )
            elif language.casefold() in {"mermaid", "mmd"}:
                diagram_derivation = derivation_record(
                    source, "mermaid_segmenter", context
                )
                diagram_id = str(diagram_derivation["id"])
                result = diagram_statement_records(
                    source,
                    "mermaid",
                    block,
                    heading_path(),
                    enclosing_role,
                    (derivation_id, diagram_id),
                    len(segments),
                    context.max_segment_chars,
                )
                diagram_derivations[diagram_id] = diagram_derivation
                segments.extend(result.segments)
                evidence.extend(result.evidence)
                warnings.extend(result.warnings)
            else:
                warnings.append(
                    warning_record(
                        source,
                        code="unsupported_construct",
                        message=(
                            "unsupported fenced code language: "
                            f"{language or '(unlabeled)'}"
                        ),
                        span=SourceSpan(line_number, cursor + 1),
                        possible_role=enclosing_role,
                        derivation_ids=(derivation_id,),
                    )
                )
            cursor += 1
            continue
        heading = HEADING.match(raw)
        if heading:
            emit_paragraph()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_levels = [item for item in heading_levels if item[0] < level]
            heading_levels.append((level, title))
            path_size = sum(len(item[1]) for item in heading_levels)
            if max(path_size, len(title), len(raw)) > context.max_segment_chars:
                warnings.append(
                    warning_record(
                        source,
                        code="segment_too_large",
                        message="Markdown heading path exceeds max_segment_chars",
                        span=SourceSpan(line_number, line_number),
                        possible_role="context",
                        derivation_ids=(derivation_id,),
                    )
                )
            else:
                segment, item_evidence = segment_and_evidence(
                    source,
                    segment_kind="heading",
                    segment_text=title,
                    evidence_text=raw,
                    span=SourceSpan(
                        line_number, line_number, 1, len(raw) + 1
                    ),
                    heading_path=heading_path(),
                    metadata={
                        "section_role": section_role(),
                        "heading_level": level,
                        "adr_id": metadata.get("id"),
                        "adr_status": metadata.get("status"),
                    },
                    derivation_ids=(derivation_id,),
                    ordinal=len(segments),
                )
                segments.append(segment)
                evidence.append(item_evidence)
            cursor += 1
            continue
        if not raw.strip():
            emit_paragraph()
        elif LIST_ITEM.match(raw):
            emit_paragraph()
            paragraph.append((line_number, raw))
            emit_paragraph()
        else:
            paragraph.append((line_number, raw))
        cursor += 1
    emit_paragraph()
    all_derivations = {derivation_id: derivation, **diagram_derivations}
    return IngestionResult(
        segments=tuple(segments),
        evidence=tuple(evidence),
        derivations=tuple(
            all_derivations[item_id] for item_id in sorted(all_derivations)
        ),
        warnings=tuple(warnings),
    )
