from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from architecture_graph.analysis_types import RecordCatalog, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.semantic_graph import GraphResult
from architecture_graph.schemas import load_versioned_resource


@dataclass(frozen=True)
class RankingResult:
    rankings: tuple[Record, ...]
    derivations: tuple[Record, ...]

    @property
    def by_node(self) -> dict[str, Record]:
        return {str(item["node_id"]): item for item in self.rankings}


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 8)


def rank_graph(graph: GraphResult, catalog: RecordCatalog) -> RankingResult:
    degree = Counter()
    for edge in graph.edges:
        degree[str(edge["from_id"])] += 1
        degree[str(edge["to_id"])] += 1
    maximum = max(degree.values(), default=1)
    rankings = []
    derivations = []
    rule_version = "scoring-v1"
    load_versioned_resource("scoring-v1.json")
    for node in graph.nodes:
        node_id = str(node["id"])
        evidence_ids = [str(x) for x in node.get("evidence_ids", [])]
        hashes = {str(catalog.get(e)["source_content_hash"]) for e in evidence_ids if catalog.maybe_get(e)}
        navigation_features = {"typed_degree": degree[node_id] / maximum, "evidence_breadth": min(1.0, len(hashes) / 3)}
        required = node.get("kind") == "claim" and (node.get("qualifiers") or {}).get("modality") == "required"
        critical_features = {"required_modality": 1.0 if required else 0.0, "evidence_breadth": min(1.0, len(hashes) / 3)}
        review_features = {"missing_rationale": 1.0 if node.get("kind") == "decision" and not node.get("rationale_evidence_ids") else 0.0, "contradiction": 1.0 if node.get("contradicting_claim_ids") else 0.0}
        confidence_features = {"tuple_completeness": 1.0 if node.get("kind") != "claim" or node.get("tuple_complete") else 0.0, "explicit_structure": 1.0 if node.get("kind") in {"source", "segment", "evidence"} else 0.7}
        vectors = {"navigation": navigation_features, "criticality": critical_features, "review_priority": review_features, "extraction_confidence": confidence_features}
        scores = {}
        for name, features in vectors.items():
            score = sum(features.values()) / max(1, len(features))
            scores[name] = {"score": _bounded(score), "features": {k: _bounded(v) for k, v in sorted(features.items())}, "rule_version": rule_version}
        derivation = build_analysis_derivation("independent_graph_scores", (node_id,), "ranking", node_id)
        derivations.append(derivation)
        rankings.append(finalize_record({"id": stable_id("ranking", node_id, rule_version, scores), "kind": "ranking", "node_id": node_id, "scores": scores, "eligible_content_hashes": sorted(hashes), "excluded_duplicate_paths": [], "evidence_ids": evidence_ids, "derivation_ids": [derivation["id"]]}))
    return RankingResult(tuple(sorted(rankings, key=lambda x: str(x["id"]))), tuple(derivations))


def rerank_decisions(graph: GraphResult, catalog: RecordCatalog, prior: RankingResult) -> RankingResult:
    fresh = rank_graph(graph, catalog)
    decision_ids = {str(node["id"]) for node in graph.nodes if node["kind"] == "decision"}
    retained = tuple(item for item in prior.rankings if item["node_id"] not in decision_ids)
    added = tuple(item for item in fresh.rankings if item["node_id"] in decision_ids)
    return RankingResult(tuple(sorted((*retained, *added), key=lambda x: str(x["id"]))), tuple((*prior.derivations, *(d for d in fresh.derivations if any(r["derivation_ids"] == [d["id"]] for r in added)))))
