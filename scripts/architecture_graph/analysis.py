from __future__ import annotations

from architecture_graph.analysis_types import AnalysisResult, RecordCatalog, analysis_identity
from architecture_graph.claims import materialize_claims
from architecture_graph.decisions import attach_decisions, reduce_decisions
from architecture_graph.decision_candidates import collect_decision_candidates
from architecture_graph.entities import resolve_entities
from architecture_graph.nlp import normalize_evidence, parse_evidence
from architecture_graph.qualifiers import qualify_relations
from architecture_graph.ranking import rank_graph, rerank_decisions
from architecture_graph.relations import extract_relation_candidates
from architecture_graph.semantic_graph import build_evidence_graph
from architecture_graph.terms import discover_terms


def analyze_catalog(phase1: RecordCatalog, *, model_name: str | None = None, tool_version: str = "0.3.1", configuration_digest: str = "sha256:" + "0" * 64, pipeline_digest: str = "sha256:" + "0" * 64) -> AnalysisResult:
    with analysis_identity(tool_version, configuration_digest, pipeline_digest):
        return _analyze_catalog(phase1, model_name=model_name)


def _analyze_catalog(phase1: RecordCatalog, *, model_name: str | None = None) -> AnalysisResult:
    parsed = parse_evidence(normalize_evidence(phase1), model_name)
    catalog = phase1.add((*parsed.warnings, *parsed.derivations))
    terms = discover_terms(parsed)
    catalog = catalog.add((*terms.terms, *terms.warnings, *terms.derivations))
    relation_result = extract_relation_candidates(parsed)
    catalog = catalog.add((*relation_result.warnings, *relation_result.derivations))
    qualified = qualify_relations(relation_result.candidates, parsed)
    entities = resolve_entities(qualified, terms)
    catalog = catalog.add((*entities.entities, *entities.warnings, *entities.derivations))
    claims = materialize_claims(qualified, entities)
    catalog = catalog.add((*claims.claims, *claims.warnings, *claims.derivations))
    base_graph = build_evidence_graph(catalog)
    base_rankings = rank_graph(base_graph, catalog)
    decision_candidates = collect_decision_candidates(parsed, catalog)
    catalog = catalog.add((*decision_candidates.warnings, *decision_candidates.derivations))
    base_graph = build_evidence_graph(catalog)
    decisions = reduce_decisions(catalog, base_graph, decision_candidates.candidates)
    graph = attach_decisions(base_graph, decisions)
    catalog = graph.catalog
    final_rankings = rerank_decisions(graph, catalog, base_rankings)
    catalog = catalog.add((*graph.edges, *final_rankings.rankings, *final_rankings.derivations))
    return AnalysisResult(catalog)
