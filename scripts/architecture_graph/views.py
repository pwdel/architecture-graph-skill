from __future__ import annotations

from collections.abc import Mapping

from architecture_graph.records import Record


_SUMMARY_FIELDS: dict[str, tuple[str, ...]] = {
    "term": ("canonical_form", "observed_forms", "term_kind", "distinct_source_count", "document_frequency", "occurrence_count", "tfidf", "discovery_signals"),
    "decision": ("title", "status", "applicability", "scope", "diagnostic_codes"),
    "entity": ("canonical_name", "entity_type"),
    "claim": ("subject", "predicate", "object", "qualifiers"),
}


def summarize_record(
    record: Record,
    rankings: Mapping[str, Record] | None = None,
    evidence_limit: int = 2,
) -> Record:
    """Return a bounded semantic-list projection without changing stored records."""
    kind = str(record.get("kind", ""))
    summary: Record = {"id": record["id"], "kind": kind}
    for field in _SUMMARY_FIELDS.get(kind, ()):
        if field in record:
            value = record[field]
            if field in {"observed_forms", "scope", "diagnostic_codes", "discovery_signals"} and isinstance(value, list):
                value = value[:8]
            summary[field] = value
    evidence_ids = [str(value) for value in record.get("evidence_ids", [])]
    derivation_ids = [str(value) for value in record.get("derivation_ids", [])]
    summary["evidence_count"] = len(evidence_ids)
    summary["top_evidence_ids"] = evidence_ids[: max(0, evidence_limit)]
    summary["derivation_count"] = len(derivation_ids)
    if rankings is not None:
        ranking = rankings.get(str(record["id"]))
        if ranking is not None:
            scores = ranking.get("scores", {})
            summary["scores"] = {name: payload.get("score", 0) for name, payload in scores.items()}
            navigation = scores.get("navigation", {})
            features = navigation.get("features", {}) if isinstance(navigation, dict) else {}
            summary["navigation_components"] = {name: features[name] for name in ("pagerank", "lexical_salience") if name in features}
    return summary
