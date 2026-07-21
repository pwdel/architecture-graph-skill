from __future__ import annotations

from collections.abc import Sequence

from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.paging import page_records
from architecture_graph.query import QueryEnvelope
from architecture_graph.records import RECORD_TYPES, Record
from architecture_graph.semantic_graph import GraphResult, bounded_neighbors
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.views import summarize_record


def _catalog(reader: SnapshotReader) -> RecordCatalog:
    return RecordCatalog.from_records(record for record_type in RECORD_TYPES for record in reader.iter(record_type))


def terms_query(reader: SnapshotReader, *, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    records = sorted((dict(x) for x in reader.iter("terms")), key=lambda x: (-float(x["tfidf"]), str(x["id"])))
    if fields is None:
        records = [summarize_record(record) for record in records]
    return page_records(records, binding={"snapshot_id": reader.snapshot_id, "command": "terms", "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def decisions_query(reader: SnapshotReader, *, score: str = "navigation", fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    if score not in {"navigation", "criticality", "review_priority", "extraction_confidence", "corroboration", "completeness"}: raise ValueError("invalid score")
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    records = []
    for decision in reader.iter("decisions"):
        item = summarize_record(dict(decision), rankings) if fields is None else dict(decision)
        ranking = rankings.get(str(item["id"]))
        if fields is not None:
            item["scores"] = {} if ranking is None else ranking["scores"]
        records.append(item)
    records.sort(key=lambda x: (-float((x.get("scores", {}).get(score) or {}).get("score", 0)), str(x["id"])))
    return page_records(records, binding={"snapshot_id": reader.snapshot_id, "command": "decisions", "score": score, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def neighbors_query(reader: SnapshotReader, *, node_id: str, depth: int = 1, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    catalog = _catalog(reader)
    graph = GraphResult(tuple(r for r in catalog.all() if r["kind"] not in {"edge", "ranking"}), catalog.iter("edge"), catalog)
    result = bounded_neighbors(graph, node_id, depth, limit)
    records = [dict(item) for item in result.nodes]
    if fields is None:
        records = [dict(item) if "depth" in item and item.get("kind") not in {"term", "entity", "claim", "decision"} else {**summarize_record(item), "depth": item.get("depth")} for item in records]
    return page_records(records, binding={"snapshot_id": reader.snapshot_id, "command": "neighbors", "node_id": node_id, "depth": depth, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def evidence_query(reader: SnapshotReader, *, record_id: str, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    catalog = _catalog(reader)
    record = catalog.get(record_id)
    evidence_ids = list(record.get("evidence_ids", []))
    records = [dict(catalog.get(str(item))) for item in evidence_ids]
    return page_records(records, binding={"snapshot_id": reader.snapshot_id, "command": "evidence", "record_id": record_id, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def explain_query(reader: SnapshotReader, *, record_id: str, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    catalog = _catalog(reader)
    record = catalog.get(record_id)
    rankings = [dict(x) for x in catalog.iter("ranking") if x.get("node_id") == record_id]
    evidence = []
    for evidence_id in record.get("evidence_ids", [])[: min(limit, 2)]:
        source = catalog.get(str(evidence_id))
        evidence.append({"id": source["id"], "path": source.get("path"), "span": source.get("span"), "text": str(source.get("text", ""))[:240]})
    derivations = []
    for derivation_id in record.get("derivation_ids", [])[: min(limit, 4)]:
        source = catalog.maybe_get(str(derivation_id))
        if source:
            derivations.append({"id": source["id"], "method": source.get("method"), "producer_kind": source.get("producer_kind")})
    scores = rankings[0].get("scores", {}) if rankings else {}
    item: Record = {"id": "explanation:" + record_id, "kind": "explanation", "record_summary": summarize_record(dict(record), {record_id: rankings[0]} if rankings else None), "scores": scores, "evidence_count": len(record.get("evidence_ids", [])), "representative_evidence": evidence, "derivation_count": len(record.get("derivation_ids", [])), "representative_derivations": derivations}
    return page_records([item], binding={"snapshot_id": reader.snapshot_id, "command": "explain", "record_id": record_id, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=1, max_chars=max_chars, cursor=cursor)
