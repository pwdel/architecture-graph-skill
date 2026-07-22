from __future__ import annotations

from architecture_graph.records import Record
from architecture_graph.paging import page_records
from architecture_graph.query import QueryEnvelope


def compose_decision_summary(base: Record, resolution: Record | None) -> Record:
    composed = dict(base)
    base_diagnostics = list(base.get("diagnostic_codes", base.get("base_diagnostics", [])))
    resolved = [] if resolution is None else list(resolution.get("resolves_diagnostics", []))
    composed["base_diagnostics"] = base_diagnostics
    composed["resolved_diagnostics"] = resolved
    composed["active_diagnostics"] = sorted(set(base_diagnostics) - set(resolved))
    if resolution is not None:
        composed["rationale_resolution"] = {
            "classification": resolution["classification"],
            "observed_roles": list(resolution.get("observed_roles", [])),
            "evidence_count": len(resolution.get("evidence_ids", [])),
            "top_evidence_ids": list(resolution.get("evidence_ids", []))[:2],
            "rule_version": resolution["rule_version"],
        }
    return composed


def rationale_find_query(
    overlay_reader,
    *,
    classification: str | None = None,
    limit: int = 20,
    max_chars: int = 12_000,
    cursor: str | None = None,
) -> QueryEnvelope:
    records = [
        {
            "id": item["id"],
            "kind": item["kind"],
            "decision_id": item["decision_id"],
            "classification": item["classification"],
            "observed_roles": item.get("observed_roles", []),
            "evidence_count": len(item.get("evidence_ids", [])),
            "resolves_diagnostics": item.get("resolves_diagnostics", []),
            "rule_version": item["rule_version"],
            "rank_eligible": item["rank_eligible"],
        }
        for item in overlay_reader.iter_resolutions()
        if classification is None or item.get("classification") == classification
    ]
    records.sort(key=lambda item: (str(item["classification"]), str(item["decision_id"])))
    return page_records(
        records,
        binding={
            "base_snapshot_id": overlay_reader.manifest["base_snapshot_id"],
            "overlay_id": overlay_reader.overlay_id,
            "command": "rationale find",
            "classification": classification,
            "projection_version": 1,
            "limit": limit,
            "max_chars": max_chars,
        },
        fields=None,
        limit=limit,
        max_chars=max_chars,
        cursor=cursor,
    )
