from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from architecture_graph.analysis_types import EvidenceUnit, ParsedSentence, RecordCatalog, build_analysis_derivation
from architecture_graph.records import Record, finalize_record


TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")
CAPITALIZED = re.compile(r"\b(?:[A-Z][A-Za-z0-9]*)(?:\s+[A-Z][A-Za-z0-9]*)*\b")
ACRONYM = re.compile(r"\b([A-Za-z][A-Za-z ]{2,})\s+\(([A-Z][A-Z0-9]{1,})\)")


@dataclass(frozen=True)
class ParsedCorpus:
    sentences: tuple[ParsedSentence, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


def _format(source: Record, segment: Record) -> str:
    metadata = segment.get("metadata", {})
    if isinstance(metadata, dict) and isinstance(metadata.get("diagram_language"), str):
        return str(metadata["diagram_language"])
    source_kind = str(source.get("source_kind", "plaintext"))
    return {"text": "plaintext", "md": "markdown", "yml": "yaml"}.get(source_kind, source_kind)


def normalize_evidence(catalog: RecordCatalog) -> tuple[EvidenceUnit, ...]:
    units: list[EvidenceUnit] = []
    for evidence in catalog.iter("evidence"):
        segment = catalog.get(str(evidence["segment_id"]))
        source = catalog.get(str(evidence["source_version_id"]))
        metadata = segment.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        derivation = build_analysis_derivation("normalize_evidence", (str(evidence["id"]),), "evidence_unit", str(evidence["id"]))
        units.append(
            EvidenceUnit(
                evidence_id=str(evidence["id"]), segment_id=str(segment["id"]),
                source_version_id=str(source["id"]), source_content_hash=str(evidence["source_content_hash"]),
                path=str(evidence["path"]), text=str(segment.get("text", evidence["text"])),
                span=evidence["span"], format_kind=_format(source, segment),
                segment_kind=str(segment["segment_kind"]), heading_path=tuple(str(x) for x in segment.get("heading_path", [])),
                section_role=str(metadata.get("section_role", "other")), document_role=str(source.get("document_role", "architecture_note")),
                authority_class=str(source.get("authority_class", "informational")),
                document_status=str((source.get("adr_metadata") or {}).get("status", "unknown")),
                adapter_name=str(source.get("adapter_name", "unknown")), metadata=metadata,
                derivation_id=str(derivation["id"]),
            )
        )
    return tuple(sorted(units, key=lambda item: item.evidence_id))


def parse_evidence(units: tuple[EvidenceUnit, ...], model_name: str | None = None) -> ParsedCorpus:
    derivations: list[Record] = []
    warnings: list[Record] = []
    if model_name:
        warning_derivation = build_analysis_derivation("rule_tokenizer_fallback", (), "warning", model_name)
        warnings.append(finalize_record({"id": "warning:model_unavailable:" + model_name, "kind": "warning", "code": "model_unavailable", "message": f"local model unavailable: {model_name}", "source_version_id": None, "span": None, "possible_role": None, "derivation_ids": [warning_derivation["id"]]}))
        derivations.append(warning_derivation)
    sentences: list[ParsedSentence] = []
    for unit in units:
        text = unicodedata.normalize("NFKC", unit.text).strip()
        derivation = build_analysis_derivation("rule_tokenizer", (unit.evidence_id,), "parsed_sentence", unit.evidence_id)
        derivations.append(derivation)
        tokens = tuple(TOKEN.findall(text))
        phrases = tuple(dict.fromkeys(CAPITALIZED.findall(text)))
        acronyms = tuple((match.group(2), match.group(1).strip()) for match in ACRONYM.finditer(text))
        sentences.append(ParsedSentence(unit.evidence_id, text, tokens, phrases, acronyms, unit.format_kind, unit.section_role, unit.source_content_hash, str(derivation["id"]), unit))
    return ParsedCorpus(tuple(sentences), tuple(warnings), tuple(sorted(derivations, key=lambda x: str(x["id"]))))
