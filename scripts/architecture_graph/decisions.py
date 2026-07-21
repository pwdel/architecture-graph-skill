from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.analysis_types import RecordCatalog, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.semantic_graph import GraphResult, _edge


@dataclass(frozen=True)
class DecisionResult:
    decisions: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


def reduce_decisions(catalog: RecordCatalog, graph: GraphResult) -> DecisionResult:
    records = []
    derivations = []
    for claim in catalog.iter("claim"):
        scope = (claim.get("qualifiers") or {}).get("scope", [])
        if not any(str(part).casefold() in {"decision", "decisions", "architecture decision"} for part in scope):
            continue
        evidence_ids = [str(x) for x in claim["evidence_ids"]]
        evidence = catalog.get(evidence_ids[0])
        source = catalog.get(str(evidence["source_version_id"]))
        status = str((source.get("adr_metadata") or {}).get("status", "unknown")).casefold()
        if status not in {"accepted", "proposed", "deprecated", "superseded", "rejected"}: status = "unknown"
        applicability = "current" if status == "accepted" else "proposed" if status == "proposed" else "historical" if status in {"deprecated", "superseded", "rejected"} else "unknown"
        title = f"{claim['subject']['surface']} {claim['predicate']} {claim['object']['surface']}"
        derivation = build_analysis_derivation("decision_reducer", (str(claim["id"]),), "decision", title)
        derivations.append(derivation)
        records.append(finalize_record({"id": stable_id("decision", title.casefold(), scope), "kind": "decision", "title": title, "status": status, "applicability": applicability, "scope": list(scope), "claim_ids": [claim["id"]], "rationale_evidence_ids": [], "consequence_evidence_ids": [], "supporting_claim_ids": [claim["id"]], "contradicting_claim_ids": [], "diagnostic_codes": ["missing_rationale"], "evidence_ids": evidence_ids, "derivation_ids": [derivation["id"]]}))
    return DecisionResult(tuple(sorted(records, key=lambda x: str(x["id"]))), (), tuple(derivations))


def attach_decisions(graph: GraphResult, decisions: DecisionResult) -> GraphResult:
    catalog = graph.catalog.add((*decisions.decisions, *decisions.derivations))
    edges = list(graph.edges)
    for decision in decisions.decisions:
        for claim_id in decision["claim_ids"]:
            edges.append(_edge("SUPPORTS", str(claim_id), str(decision["id"]), decision["evidence_ids"], decision["derivation_ids"]))
    nodes = tuple(record for record in catalog.all() if record["kind"] in {"source", "segment", "evidence", "term", "entity", "claim", "decision", "warning", "derivation"})
    return GraphResult(tuple(sorted(nodes, key=lambda x: str(x["id"]))), tuple(sorted(edges, key=lambda x: str(x["id"]))), catalog)
