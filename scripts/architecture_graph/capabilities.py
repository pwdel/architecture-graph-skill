from architecture_graph.records import Record, finalize_record
from architecture_graph.schemas import EDGE_TYPES, NODE_TYPES, SCORE_TYPES


def capability_record() -> Record:
    return finalize_record(
        {
            "id": "capability:phase2",
            "kind": "capability",
            "schema_version": 1,
            "phases": ["phase1", "phase2"],
            "commands": [
                "capabilities", "decisions", "evidence", "explain", "find",
                "get", "index", "memory status", "neighbors", "report", "terms",
            ],
            "record_types": ["claim", "decision", "derivation", "edge", "entity", "evidence", "ranking", "segment", "source", "term", "warning"],
            "node_types": sorted(NODE_TYPES),
            "edge_types": sorted(EDGE_TYPES),
            "scores": sorted(SCORE_TYPES),
            "provenance_layers": ["deterministic"],
            "rule_versions": ["decision-rules-v1", "entity-rules-v1", "extraction-rules-en-v1", "predicates-v1", "scoring-v1", "terms-en-v1"],
            "unavailable": ["human_review_mutation", "image_interpretation", "semantic_snapshot_diff", "decision_lineage"],
        }
    )
