from __future__ import annotations

from architecture_graph.ingest import IngestionContext, IngestionResult
from architecture_graph.ingest.diagrams import (
    derivation_record,
    exact_source_excerpt,
    segment_and_evidence,
    warning_record,
)
from architecture_graph.records import Record, SourceSpan
from architecture_graph.sources import SourceInput


def _bounded_paragraphs(
    paragraph: list[tuple[int, str]], max_chars: int, source: SourceInput
) -> list[tuple[str, str, SourceSpan]]:
    normalized = " ".join(raw.strip() for _, raw in paragraph)
    paragraph_span = SourceSpan(
        paragraph[0][0],
        paragraph[-1][0],
        1,
        len(paragraph[-1][1]) + 1,
    )
    paragraph_evidence = exact_source_excerpt(source, paragraph_span)
    if max(len(normalized), len(paragraph_evidence)) <= max_chars:
        return [(normalized, paragraph_evidence, paragraph_span)]

    chunks: list[tuple[str, str, SourceSpan]] = []
    for line_number, raw in paragraph:
        content_start = len(raw) - len(raw.lstrip())
        content_end = len(raw.rstrip())
        for window_start in range(content_start, content_end, max_chars):
            window_end = min(content_end, window_start + max_chars)
            start = window_start
            end = window_end
            while start < end and raw[start].isspace():
                start += 1
            while end > start and raw[end - 1].isspace():
                end -= 1
            if start == end:
                continue
            span = SourceSpan(line_number, line_number, start + 1, end + 1)
            evidence_text = exact_source_excerpt(source, span)
            chunks.append((evidence_text, evidence_text, span))
    return chunks


def segment_plaintext(
    source: SourceInput, context: IngestionContext
) -> IngestionResult:
    if source.source_kind != "text":
        raise ValueError(
            f"plain-text adapter does not accept source kind: {source.source_kind}"
        )
    derivation = derivation_record(source, "plaintext_segmenter", context)
    derivation_id = str(derivation["id"])
    if source.decode_error is not None:
        warning = warning_record(
            source,
            code="parse_failed",
            message=source.decode_error,
            span=None,
            possible_role="context",
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))

    paragraphs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for line_number, raw in enumerate(source.text.splitlines(), start=1):
        if raw.strip():
            current.append((line_number, raw))
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)

    segments: list[Record] = []
    evidence: list[Record] = []
    for paragraph in paragraphs:
        for text, evidence_text, span in _bounded_paragraphs(
            paragraph, context.max_segment_chars, source
        ):
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind="paragraph",
                segment_text=text,
                evidence_text=evidence_text,
                span=span,
                heading_path=(),
                metadata={"section_role": "context"},
                derivation_ids=(derivation_id,),
                ordinal=len(segments),
            )
            segments.append(segment)
            evidence.append(item_evidence)
    return IngestionResult(
        segments=tuple(segments),
        evidence=tuple(evidence),
        derivations=(derivation,),
    )
