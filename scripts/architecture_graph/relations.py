from __future__ import annotations

from dataclasses import dataclass
import re

from architecture_graph.analysis_types import RelationCandidate
from architecture_graph.nlp import ParsedCorpus
from architecture_graph.analysis_types import build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.schemas import load_versioned_resource


@dataclass(frozen=True)
class RelationResult:
    candidates: tuple[RelationCandidate, ...]
    warnings: tuple[Record, ...] = ()
    derivations: tuple[Record, ...] = ()


def extract_relation_candidates(parsed: ParsedCorpus) -> RelationResult:
    surfaces = load_versioned_resource("predicates-v1.json")["canonical_predicates"]
    candidates: list[RelationCandidate] = []
    warnings: list[Record] = []
    derivations: list[Record] = []
    for sentence in parsed.sentences:
        text = sentence.text.strip().rstrip(".!?")
        matched = False
        if sentence.format_kind in {"mermaid", "plantuml"}:
            diagram = re.match(r"^\s*([^\s]+)\s*(?:-->|->|\.\.>)\s*(?:\|([^|]+)\|\s*)?([^\s:]+)(?:\s*:\s*(.+))?$", text)
            if diagram:
                subject, inline_label, target, trailing_label = diagram.groups()
                label = (inline_label or trailing_label or "").strip()
                for predicate, variants in surfaces.items():
                    if any(re.search(rf"\b{re.escape(variant)}\b", label, re.IGNORECASE) for variant in variants):
                        candidates.append(RelationCandidate(subject, str(predicate), target, sentence.evidence_id, sentence, "diagram_edge", True))
                        matched = True
                        break
                if matched:
                    continue
        for predicate, variants in surfaces.items():
            for variant in sorted(variants, key=len, reverse=True):
                match = re.search(rf"\b{re.escape(variant)}\b", text, re.IGNORECASE)
                if match:
                    subject_words = text[:match.start()].strip().split()
                    while subject_words and subject_words[-1].casefold() in {"must", "shall", "may", "might", "should"}:
                        subject_words.pop()
                    subject = subject_words[-1] if subject_words else None
                    object_text = text[match.end():].strip()
                    object_value = object_text.split()[0] if object_text else None
                    candidates.append(RelationCandidate(subject, str(predicate), object_value, sentence.evidence_id, sentence, "diagram_edge" if sentence.format_kind in {"mermaid", "plantuml"} else "rule_prose", bool(subject and object_value)))
                    matched = True
                    break
            if matched: break
        if matched and candidates[-1].sentence.evidence_id == sentence.evidence_id and not candidates[-1].tuple_complete:
            derivation = build_analysis_derivation("relation_diagnostic", (sentence.evidence_id,), "warning", sentence.evidence_id + ":incomplete")
            derivations.append(derivation)
            warnings.append(finalize_record({"id": stable_id("warning", "incomplete_relation", sentence.evidence_id), "kind": "warning", "code": "incomplete_relation", "message": "relation candidate is missing a subject or object", "source_version_id": sentence.unit.source_version_id, "span": dict(sentence.unit.span), "possible_role": sentence.section_role, "derivation_ids": [derivation["id"]]}))
        if not matched:
            derivation = build_analysis_derivation("relation_diagnostic", (sentence.evidence_id,), "warning", sentence.evidence_id)
            derivations.append(derivation)
            warnings.append(finalize_record({"id": stable_id("warning", "unmatched_relation", sentence.evidence_id), "kind": "warning", "code": "unmatched_relation", "message": "no complete controlled relation was extracted", "source_version_id": sentence.unit.source_version_id, "span": dict(sentence.unit.span), "possible_role": sentence.section_role, "derivation_ids": [derivation["id"]]}))
    return RelationResult(tuple(candidates), tuple(warnings), tuple(derivations))
