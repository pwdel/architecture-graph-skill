from __future__ import annotations

import re

import yaml

from architecture_graph.ingest import IngestionResult
from architecture_graph.ingest.diagrams import (
    derivation_record,
    diagram_statement_records,
    segment_and_evidence,
    warning_record,
)
from architecture_graph.records import Record, SourceSpan
from architecture_graph.sources import SourceInput


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_OPEN = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
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


def segment_markdown(source: SourceInput) -> IngestionResult:
    derivation = derivation_record(source, "markdown_segmenter")
    derivation_id = str(derivation["id"])
    if source.decode_error is not None:
        warning = warning_record(
            source,
            code="parse_failed",
            message=source.decode_error,
            span=None,
            possible_role=None,
            derivation_id=derivation_id,
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))

    lines = source.text.splitlines()
    metadata: dict[str, object] = {}
    metadata_lines: dict[str, int] = {}
    cursor = 0
    if lines and lines[0].strip() == "---":
        try:
            closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
            raw_metadata = yaml.safe_load("\n".join(lines[1:closing])) or {}
            if isinstance(raw_metadata, dict):
                metadata = {str(key): value for key, value in raw_metadata.items()}
                for index, raw_line in enumerate(lines[1:closing], start=2):
                    match = re.match(r"^([A-Za-z0-9_-]+)\s*:", raw_line)
                    if match and match.group(1) not in metadata_lines:
                        metadata_lines[match.group(1)] = index
            cursor = closing + 1
        except (StopIteration, yaml.YAMLError) as error:
            warning = warning_record(
                source,
                code="unsupported_construct",
                message=f"invalid Markdown front matter: {error}",
                span=SourceSpan(1, min(len(lines), 2)),
                possible_role="status",
                derivation_id=derivation_id,
            )
            return IngestionResult(derivations=(derivation,), warnings=(warning,))

    heading_levels: list[tuple[int, str]] = []
    segments: list[Record] = []
    evidence: list[Record] = []
    warnings: list[Record] = []
    paragraph: list[tuple[int, str]] = []

    for key in ("id", "status"):
        if key not in metadata or key not in metadata_lines:
            continue
        line_number = metadata_lines[key]
        text = lines[line_number - 1].strip()
        segment, item_evidence = segment_and_evidence(
            source,
            segment_kind="metadata_field",
            text=text,
            span=SourceSpan(line_number, line_number),
            heading_path=(),
            metadata={
                "section_role": "status" if key == "status" else "context",
                "metadata_key": key,
                "metadata_value": metadata[key],
                "adr_id": metadata.get("id"),
                "adr_status": metadata.get("status"),
            },
            derivation_id=derivation_id,
            ordinal=len(segments),
        )
        segments.append(segment)
        evidence.append(item_evidence)

    def heading_path() -> list[str]:
        return [title for _, title in heading_levels]

    def section_role() -> str:
        if not heading_levels:
            return "context"
        return SECTION_ROLES.get(heading_levels[-1][1].strip().casefold(), "context")

    def emit_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(line.strip() for _, line in paragraph).strip()
        if text:
            span = SourceSpan(paragraph[0][0], paragraph[-1][0])
            segment_kind = "list_item" if paragraph[0][1].lstrip().startswith(("- ", "* ")) else "paragraph"
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind=segment_kind,
                text=text,
                span=span,
                heading_path=heading_path(),
                metadata={
                    "section_role": section_role(),
                    "adr_id": metadata.get("id"),
                    "adr_status": metadata.get("status"),
                },
                derivation_id=derivation_id,
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
                        derivation_id=derivation_id,
                    )
                )
            elif language.casefold() in {"mermaid", "mmd"}:
                result = diagram_statement_records(
                    source,
                    "mermaid",
                    block,
                    heading_path(),
                    enclosing_role,
                    derivation_id,
                    len(segments),
                )
                segments.extend(result.segments)
                evidence.extend(result.evidence)
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
                        derivation_id=derivation_id,
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
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind="heading",
                text=title,
                span=SourceSpan(line_number, line_number, 1, len(raw) + 1),
                heading_path=heading_path(),
                metadata={
                    "section_role": section_role(),
                    "heading_level": level,
                    "adr_id": metadata.get("id"),
                    "adr_status": metadata.get("status"),
                },
                derivation_id=derivation_id,
                ordinal=len(segments),
            )
            segments.append(segment)
            evidence.append(item_evidence)
            cursor += 1
            continue
        if not raw.strip():
            emit_paragraph()
        elif raw.lstrip().startswith(("- ", "* ")):
            emit_paragraph()
            paragraph.append((line_number, raw))
            emit_paragraph()
        else:
            paragraph.append((line_number, raw))
        cursor += 1
    emit_paragraph()
    return IngestionResult(
        segments=tuple(segments),
        evidence=tuple(evidence),
        derivations=(derivation,),
        warnings=tuple(warnings),
    )
