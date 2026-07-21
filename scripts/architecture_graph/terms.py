from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict
import math

from architecture_graph.analysis_types import build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.nlp import ParsedCorpus
from architecture_graph.records import Record, finalize_record
from architecture_graph.schemas import load_versioned_resource


@dataclass(frozen=True)
class TermResult:
    terms: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]
    weights_by_evidence_id: dict[str, dict[str, float]]


def discover_terms(parsed: ParsedCorpus) -> TermResult:
    stop = set(load_versioned_resource("terms-en-v1.json")["stop_words"])
    docs: dict[str, Counter[str]] = defaultdict(Counter)
    evidence: dict[str, set[str]] = defaultdict(set)
    forms: dict[str, set[str]] = defaultdict(set)
    signals: dict[str, set[str]] = defaultdict(lambda: {"tfidf"})
    for sentence in parsed.sentences:
        candidates = [token for token in sentence.tokens if token.casefold() not in stop and len(token) > 2]
        candidates.extend(sentence.noun_phrases)
        for raw in candidates:
            canonical = " ".join(raw.casefold().split())
            docs[sentence.source_content_hash][canonical] += 1
            evidence[canonical].add(sentence.evidence_id)
            forms[canonical].add(raw)
            if sentence.section_role == "glossary": signals[canonical].add("explicit_glossary")
        for acronym, expansion in sentence.acronyms:
            signals[acronym.casefold()].add("acronym")
            forms[acronym.casefold()].add(acronym)
            evidence[acronym.casefold()].add(sentence.evidence_id)
            docs[sentence.source_content_hash][acronym.casefold()] += 1
    document_count = max(1, len(docs))
    terms: list[Record] = []
    derivations: list[Record] = []
    weights: dict[str, dict[str, float]] = defaultdict(dict)
    for term in sorted(evidence):
        present = [digest for digest, counts in docs.items() if counts[term]]
        idf = math.log((1 + document_count) / (1 + len(present))) + 1
        score = max((1 + math.log(docs[digest][term])) * idf for digest in present)
        derivation = build_analysis_derivation("sparse_tfidf", tuple(sorted(evidence[term])), "term", term)
        derivations.append(derivation)
        record = finalize_record({"id": stable_id("term", term), "kind": "term", "canonical_form": term, "observed_forms": sorted(forms[term]), "term_kind": "acronym" if "acronym" in signals[term] else "noun_phrase", "distinct_source_count": len(present), "document_frequency": len(present), "tfidf": round(score, 8), "discovery_signals": sorted(signals[term]), "evidence_ids": sorted(evidence[term]), "derivation_ids": [derivation["id"]]})
        terms.append(record)
        for evidence_id in evidence[term]: weights[evidence_id][term] = round(score, 8)
    return TermResult(tuple(terms), (), tuple(derivations), dict(weights))
