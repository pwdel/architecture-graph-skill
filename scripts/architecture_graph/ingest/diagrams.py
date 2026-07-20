from __future__ import annotations

from collections.abc import Sequence
import re

from architecture_graph.canonical import stable_id
from architecture_graph.ingest import IngestionContext, IngestionResult
from architecture_graph.records import Record, SourceSpan, finalize_record
from architecture_graph.sources import SourceInput, source_record_id


ARROW = re.compile(r"<--|-->|\.\.>|->")


def exact_source_excerpt(source: SourceInput, span: SourceSpan) -> str:
    if span.end_column is None:
        raise ValueError("exact evidence spans require an exclusive end column")
    lines = source.text.splitlines(keepends=True)
    if span.start_line > len(lines) or span.end_line > len(lines):
        raise ValueError("evidence span exceeds source lines")

    def content_length(raw: str) -> int:
        if raw.endswith("\r\n"):
            return len(raw) - 2
        if raw.endswith(("\r", "\n")):
            return len(raw) - 1
        return len(raw)

    first = lines[span.start_line - 1]
    last = lines[span.end_line - 1]
    if span.start_column > content_length(first) + 1:
        raise ValueError("evidence start column exceeds source line")
    if span.end_column > content_length(last) + 1:
        raise ValueError("evidence end column exceeds source line")

    start_offset = sum(len(line) for line in lines[: span.start_line - 1])
    start_offset += span.start_column - 1
    end_offset = sum(len(line) for line in lines[: span.end_line - 1])
    end_offset += span.end_column - 1
    return source.text[start_offset:end_offset]


def derivation_record(
    source: SourceInput, method: str, context: IngestionContext
) -> Record:
    source_id = source_record_id(source)
    derivation_id = stable_id(
        "derivation",
        "deterministic",
        method,
        context.tool_version,
        context.configuration_digest,
        context.pipeline_digest,
        source_id,
        "segment_set",
        source_id,
    )
    return finalize_record(
        {
            "id": derivation_id,
            "kind": "derivation",
            "producer_kind": "deterministic",
            "method": method,
            "tool": "architecture-graph",
            "tool_version": context.tool_version,
            "model": None,
            "model_version": None,
            "model_artifact_digest": None,
            "configuration_digest": context.configuration_digest,
            "pipeline_digest": context.pipeline_digest,
            "input_ids": [source_id],
            "output_kind": "segment_set",
            "output_identity_key": source_id,
            "created_at": None,
        }
    )


def segment_and_evidence(
    source: SourceInput,
    *,
    segment_kind: str,
    segment_text: str,
    evidence_text: str,
    span: SourceSpan,
    heading_path: Sequence[str],
    metadata: dict[str, object],
    derivation_ids: Sequence[str],
    ordinal: int,
) -> tuple[Record, Record]:
    if evidence_text != exact_source_excerpt(source, span):
        raise ValueError("evidence text does not match its exact source span")
    source_id = source_record_id(source)
    canonical_derivations = sorted(set(derivation_ids))
    segment_id = stable_id(
        "segment", source_id, segment_kind, list(heading_path), ordinal, span.as_record()
    )
    evidence_id = stable_id(
        "evidence",
        source.relative_path,
        source.content_hash,
        span.as_record(),
        segment_id,
    )
    segment = finalize_record(
        {
            "id": segment_id,
            "kind": "segment",
            "source_version_id": source_id,
            "segment_kind": segment_kind,
            "heading_path": list(heading_path),
            "ordinal": ordinal,
            "text": segment_text,
            "span": span.as_record(),
            "metadata": metadata,
            "evidence_ids": [evidence_id],
            "derivation_ids": canonical_derivations,
        }
    )
    evidence = finalize_record(
        {
            "id": evidence_id,
            "kind": "evidence",
            "source_version_id": source_id,
            "segment_id": segment_id,
            "path": source.relative_path,
            "source_content_hash": source.content_hash,
            "span": span.as_record(),
            "text": evidence_text,
            "derivation_ids": canonical_derivations,
        }
    )
    return segment, evidence


def warning_record(
    source: SourceInput,
    *,
    code: str,
    message: str,
    span: SourceSpan | None,
    possible_role: str | None,
    derivation_ids: Sequence[str],
) -> Record:
    return finalize_record(
        {
            "id": stable_id("warning", source_record_id(source), code, message, span),
            "kind": "warning",
            "code": code,
            "message": message,
            "source_version_id": source_record_id(source),
            "span": None if span is None else span.as_record(),
            "possible_role": possible_role,
            "derivation_ids": sorted(set(derivation_ids)),
        }
    )


def diagram_statement_records(
    source: SourceInput,
    language: str,
    lines: Sequence[tuple[int, str]],
    heading_path: Sequence[str],
    section_role: str,
    derivation_ids: Sequence[str],
    ordinal_start: int,
    max_segment_chars: int,
    adr_id: object | None,
    adr_status: object | None,
) -> IngestionResult:
    segments: list[Record] = []
    evidence: list[Record] = []
    warnings: list[Record] = []
    ignored_prefixes = ("graph ", "flowchart ", "sequenceDiagram", "@startuml", "@enduml")

    def statement_ranges(raw: str) -> list[tuple[int, int]] | None:
        ranges: list[tuple[int, int]] = []
        opening_for = {
            "]": "[",
            ")": "(",
            "}": "{",
        }
        stack: list[str] = []
        quote: str | None = None
        escaped = False
        pipe_label = False
        start = 0
        for index, character in enumerate(raw):
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                continue
            if character in {'"', "'"}:
                quote = character
            elif character == "|" and not stack:
                pipe_label = not pipe_label
            elif pipe_label:
                continue
            elif character in "[({":
                stack.append(character)
            elif character in "])}":
                if not stack or stack.pop() != opening_for[character]:
                    return None
            elif character == ";" and not stack:
                ranges.append((start, index))
                start = index + 1
        if quote is not None or stack or pipe_label:
            return None
        ranges.append((start, len(raw)))
        return ranges

    def trimmed_range(raw: str, start: int, end: int) -> tuple[int, int]:
        while start < end and raw[start].isspace():
            start += 1
        while end > start and raw[end - 1].isspace():
            end -= 1
        return start, end

    for line_number, raw in lines:
        text = raw.strip()
        if not text or text.startswith(("%%", "'")) or text.startswith(ignored_prefixes):
            continue
        if ARROW.search(text) is None:
            continue
        ranges = statement_ranges(raw)
        candidates: list[tuple[int, int]] = []
        if ranges is not None:
            for start, end in ranges:
                start, end = trimmed_range(raw, start, end)
                if start < end and ARROW.search(raw[start:end]) is not None:
                    candidates.append((start, end))
        if ranges is None or any(
            len(ARROW.findall(raw[start:end])) != 1 for start, end in candidates
        ):
            warnings.append(
                warning_record(
                    source,
                    code="unsupported_construct",
                    message="unsplittable compound Mermaid statement",
                    span=SourceSpan(line_number, line_number, 1, len(raw) + 1),
                    possible_role=section_role,
                    derivation_ids=derivation_ids,
                )
            )
            continue
        for start, end in candidates:
            statement = raw[start:end]
            span = SourceSpan(line_number, line_number, start + 1, end + 1)
            if len(statement) > max_segment_chars:
                warnings.append(
                    warning_record(
                        source,
                        code="segment_too_large",
                        message=(
                            f"{language} statement exceeds max_segment_chars "
                            f"at line {line_number}"
                        ),
                        span=span,
                        possible_role=section_role,
                        derivation_ids=derivation_ids,
                    )
                )
                continue
            metadata: dict[str, object] = {
                "diagram_language": language,
                "content_role": "diagram",
                "section_role": section_role,
            }
            if adr_id is not None:
                metadata["adr_id"] = adr_id
            if adr_status is not None:
                metadata["adr_status"] = adr_status
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind="diagram_statement",
                segment_text=statement,
                evidence_text=statement,
                span=span,
                heading_path=heading_path,
                metadata=metadata,
                derivation_ids=derivation_ids,
                ordinal=ordinal_start + len(segments),
            )
            segments.append(segment)
            evidence.append(item_evidence)
    return IngestionResult(
        segments=tuple(segments),
        evidence=tuple(evidence),
        warnings=tuple(warnings),
    )


def segment_diagram(
    source: SourceInput,
    context: IngestionContext,
    language: str | None = None,
) -> IngestionResult:
    selected_language = language or source.source_kind
    if selected_language not in {"mermaid", "plantuml"}:
        raise ValueError(f"unsupported diagram language: {selected_language}")
    derivation = derivation_record(source, f"{selected_language}_segmenter", context)
    derivation_id = str(derivation["id"])
    if source.decode_error is not None:
        warning = warning_record(
            source,
            code="parse_failed",
            message=source.decode_error,
            span=None,
            possible_role="diagram",
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))
    result = diagram_statement_records(
        source,
        selected_language,
        list(enumerate(source.text.splitlines(), start=1)),
        (),
        "diagram",
        (derivation_id,),
        0,
        context.max_segment_chars,
        None,
        None,
    )
    if source.text.strip() and not result.segments and not result.warnings:
        warning = warning_record(
            source,
            code="unsupported_construct",
            message=(
                f"no supported {selected_language} relationship statements found"
            ),
            span=SourceSpan(1, max(1, len(source.text.splitlines()))),
            possible_role="diagram",
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))
    return IngestionResult(
        segments=result.segments,
        evidence=result.evidence,
        derivations=(derivation,),
        warnings=result.warnings,
    )
