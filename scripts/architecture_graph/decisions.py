from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.analysis_types import DecisionCandidate, RecordCatalog, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.semantic_graph import GraphResult, _edge


@dataclass(frozen=True)
class DecisionResult:
    decisions: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


def reduce_decisions(catalog: RecordCatalog, graph: GraphResult, candidates: tuple[DecisionCandidate, ...] = ()) -> DecisionResult:
    grouped: dict[tuple[str, tuple[str, ...]], list[Record]] = {}
    derivations = []
    for claim in catalog.iter("claim"):
        scope = (claim.get("qualifiers") or {}).get("scope", [])
        if not any(str(part).casefold() in {"decision", "decisions", "architecture decision"} for part in scope):
            continue
        title = f"{claim['subject']['surface']} {claim['predicate']} {claim['object']['surface']}"
        grouped.setdefault((title, tuple(str(x) for x in scope)), []).append(claim)
    records = []
    for candidate in candidates:
        fields = candidate.field_roles
        title = fields.get("title") or fields["decision"]
        status = candidate.status if candidate.status in {"accepted", "proposed", "deprecated", "superseded", "rejected"} else "unknown"
        applicability = "current" if status == "accepted" else "proposed" if status == "proposed" else "historical" if status in {"deprecated", "superseded", "rejected"} else "unknown"
        missing = sorted(f"missing_{role}" for role in ("rationale", "consequences", "scope") if role not in fields)
        records.append(finalize_record({"id": stable_id("decision", title.casefold(), candidate.scope), "kind": "decision", "title": title, "statement": fields["decision"], "status": status, "applicability": applicability, "scope": list(candidate.scope), "claim_ids": [], "rationale_evidence_ids": list(candidate.field_evidence_ids.get("rationale", ())), "consequence_evidence_ids": list(candidate.field_evidence_ids.get("consequences", ())), "supporting_claim_ids": [], "contradicting_claim_ids": [], "diagnostic_codes": missing, "anchor_kind": candidate.anchor_kind, "parser_provenance": candidate.parser_provenance, "field_roles": dict(fields), "evidence_ids": list(candidate.evidence_ids), "derivation_ids": list(candidate.derivation_ids)}))
    for (title, scope), claims in sorted(grouped.items()):
        claim = claims[0]
        evidence_ids = sorted({str(e) for item in claims for e in item["evidence_ids"]})
        evidence = catalog.get(evidence_ids[0])
        source = catalog.get(str(evidence["source_version_id"]))
        status = str((source.get("adr_metadata") or {}).get("status", "unknown")).casefold()
        if status not in {"accepted", "proposed", "deprecated", "superseded", "rejected"}: status = "unknown"
        applicability = "current" if status == "accepted" else "proposed" if status == "proposed" else "historical" if status in {"deprecated", "superseded", "rejected"} else "unknown"
        claim_ids = sorted(str(item["id"]) for item in claims)
        derivation = build_analysis_derivation("decision_reducer", claim_ids, "decision", title)
        derivations.append(derivation)
        records.append(finalize_record({"id": stable_id("decision", title.casefold(), scope), "kind": "decision", "title": title, "statement": title, "status": status, "applicability": applicability, "scope": list(scope), "claim_ids": claim_ids, "rationale_evidence_ids": [], "consequence_evidence_ids": [], "supporting_claim_ids": claim_ids, "contradicting_claim_ids": [], "diagnostic_codes": ["missing_rationale"], "anchor_kind": "decision_heading", "parser_provenance": "qualified_claim", "field_roles": {"decision": title}, "evidence_ids": evidence_ids, "derivation_ids": [derivation["id"]]}))
    return DecisionResult(tuple(sorted(records, key=lambda x: str(x["id"]))), (), tuple(derivations))


def attach_decisions(graph: GraphResult, decisions: DecisionResult) -> GraphResult:
    catalog = graph.catalog.add((*decisions.decisions, *decisions.derivations))
    edges = list(graph.edges)
    for decision in decisions.decisions:
        for claim_id in decision["claim_ids"]:
            edges.append(_edge("SUPPORTS", str(claim_id), str(decision["id"]), decision["evidence_ids"], decision["derivation_ids"]))
    nodes = tuple(record for record in catalog.all() if record["kind"] in {"source", "segment", "evidence", "term", "entity", "claim", "decision", "warning", "derivation"})
    return GraphResult(tuple(sorted(nodes, key=lambda x: str(x["id"]))), tuple(sorted(edges, key=lambda x: str(x["id"]))), catalog)
