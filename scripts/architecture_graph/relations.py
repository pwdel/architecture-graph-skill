from __future__ import annotations

from dataclasses import dataclass
import re

from architecture_graph.analysis_types import RelationCandidate
from architecture_graph.nlp import ParsedCorpus
from architecture_graph.records import Record
from architecture_graph.schemas import load_versioned_resource


@dataclass(frozen=True)
class RelationResult:
    candidates: tuple[RelationCandidate, ...]
    warnings: tuple[Record, ...] = ()
    derivations: tuple[Record, ...] = ()


def extract_relation_candidates(parsed: ParsedCorpus) -> RelationResult:
    surfaces = load_versioned_resource("predicates-v1.json")["canonical_predicates"]
    candidates: list[RelationCandidate] = []
    for sentence in parsed.sentences:
        text = sentence.text.strip().rstrip(".!?")
        matched = False
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
    return RelationResult(tuple(candidates))
