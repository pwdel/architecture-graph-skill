from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.analysis_types import QualifiedRelation, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.terms import TermResult


@dataclass(frozen=True)
class EntityResult:
    entities: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]
    by_key: dict[str, Record]


def resolve_entities(relations: tuple[QualifiedRelation, ...], terms: TermResult) -> EntityResult:
    evidence: dict[str, set[str]] = {}
    forms: dict[str, set[str]] = {}
    for relation in relations:
        for surface in (relation.candidate.subject, relation.candidate.object):
            if not surface: continue
            key = " ".join(surface.casefold().split())
            evidence.setdefault(key, set()).add(relation.candidate.evidence_id)
            forms.setdefault(key, set()).add(surface)
    records = []
    derivations = []
    for key in sorted(evidence):
        derivation = build_analysis_derivation("exact_entity_key", tuple(evidence[key]), "entity", key)
        derivations.append(derivation)
        records.append(finalize_record({"id": stable_id("entity", key), "kind": "entity", "canonical_key": key, "name": sorted(forms[key])[0], "entity_type": "concept", "observed_forms": sorted(forms[key]), "evidence_ids": sorted(evidence[key]), "derivation_ids": [derivation["id"]]}))
    return EntityResult(tuple(records), (), tuple(derivations), {str(x["canonical_key"]): x for x in records})
