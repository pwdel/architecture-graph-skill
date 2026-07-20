from __future__ import annotations

from collections.abc import Sequence

from architecture_graph.canonical import stable_id
from architecture_graph.ingest import IngestionResult
from architecture_graph.records import Record, SourceSpan, finalize_record
from architecture_graph.sources import SourceInput, source_record_id


CHECKPOINT_DIGEST = "sha256:" + ("0" * 64)


def derivation_record(source: SourceInput, method: str) -> Record:
    source_id = source_record_id(source)
    derivation_id = stable_id(
        "derivation",
        "deterministic",
        method,
        "v1",
        CHECKPOINT_DIGEST,
        CHECKPOINT_DIGEST,
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
            "tool_version": "0.1.0",
            "model": None,
            "model_version": None,
            "model_artifact_digest": None,
            "configuration_digest": CHECKPOINT_DIGEST,
            "pipeline_digest": CHECKPOINT_DIGEST,
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
    text: str,
    span: SourceSpan,
    heading_path: Sequence[str],
    metadata: dict[str, object],
    derivation_id: str,
    ordinal: int,
) -> tuple[Record, Record]:
    source_id = source_record_id(source)
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
            "text": text,
            "span": span.as_record(),
            "metadata": metadata,
            "evidence_ids": [evidence_id],
            "derivation_ids": [derivation_id],
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
            "text": text,
            "derivation_ids": [derivation_id],
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
    derivation_id: str,
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
            "derivation_ids": [derivation_id],
        }
    )


def diagram_statement_records(
    source: SourceInput,
    language: str,
    lines: Sequence[tuple[int, str]],
    heading_path: Sequence[str],
    section_role: str,
    derivation_id: str,
    ordinal_start: int,
) -> IngestionResult:
    segments: list[Record] = []
    evidence: list[Record] = []
    ignored_prefixes = ("graph ", "flowchart ", "sequenceDiagram", "@startuml", "@enduml")
    for line_number, raw in lines:
        text = raw.strip()
        if not text or text.startswith(("%%", "'")) or text.startswith(ignored_prefixes):
            continue
        if not any(token in text for token in ("-->", "->", "<--", "..>")):
            continue
        span = SourceSpan(line_number, line_number, raw.index(text) + 1, len(raw) + 1)
        segment, item_evidence = segment_and_evidence(
            source,
            segment_kind="diagram_statement",
            text=text,
            span=span,
            heading_path=heading_path,
            metadata={
                "diagram_language": language,
                "content_role": "diagram",
                "section_role": section_role,
            },
            derivation_id=derivation_id,
            ordinal=ordinal_start + len(segments),
        )
        segments.append(segment)
        evidence.append(item_evidence)
    return IngestionResult(tuple(segments), tuple(evidence))
