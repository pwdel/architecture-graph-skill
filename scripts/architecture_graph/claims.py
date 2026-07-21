from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.analysis_types import QualifiedRelation, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.entities import EntityResult
from architecture_graph.records import Record, finalize_record


@dataclass(frozen=True)
class ClaimResult:
    claims: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


def materialize_claims(relations: tuple[QualifiedRelation, ...], entities: EntityResult) -> ClaimResult:
    claims = []
    derivations = []
    for relation in relations:
        candidate = relation.candidate
        if not candidate.tuple_complete or not candidate.subject or not candidate.object or not candidate.predicate:
            continue
        subject = entities.by_key[candidate.subject.casefold()]
        object_record = entities.by_key[candidate.object.casefold()]
        identity = (subject["id"], candidate.predicate, object_record["id"], relation.modality, relation.polarity, relation.applicability, candidate.evidence_id)
        derivation = build_analysis_derivation("qualified_relation", (candidate.evidence_id,), "claim", str(identity))
        derivations.append(derivation)
        claims.append(finalize_record({"id": stable_id("claim", *identity), "kind": "claim", "subject": {"kind": "entity_ref", "surface": candidate.subject, "entity_id": subject["id"]}, "predicate": candidate.predicate, "object": {"kind": "entity_ref", "surface": candidate.object, "entity_id": object_record["id"]}, "qualifiers": {"modality": relation.modality, "polarity": relation.polarity, "conditions": list(relation.conditions), "scope": list(relation.scope), "time_applicability": relation.time_applicability, "applicability": relation.applicability}, "tuple_complete": True, "parser_provenance": candidate.parser_provenance, "evidence_ids": [candidate.evidence_id], "derivation_ids": [derivation["id"]]}))
    return ClaimResult(tuple(sorted(claims, key=lambda x: str(x["id"]))), (), tuple(derivations))
