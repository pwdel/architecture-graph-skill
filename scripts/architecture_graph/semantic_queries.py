from __future__ import annotations

from collections.abc import Sequence

from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.paging import page_records
from architecture_graph.query import QueryEnvelope
from architecture_graph.records import RECORD_TYPES, Record
from architecture_graph.semantic_graph import GraphResult, bounded_neighbors
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.views import summarize_record
from architecture_graph.overlay_queries import compose_decision_summary


def _coverage(reader: SnapshotReader) -> Record:
    sources = tuple(reader.iter("sources"))
    segments = tuple(reader.iter("segments"))
    decisions = tuple(reader.iter("decisions"))
    structured_parents: set[tuple[str, str]] = set()
    for segment in segments:
        metadata = segment.get("metadata", {})
        pointer = metadata.get("json_pointer") if isinstance(metadata, dict) else None
        if isinstance(pointer, str) and pointer.casefold().endswith("/decision"):
            structured_parents.add((str(segment.get("source_version_id")), pointer.rsplit("/", 1)[0]))
    return {
        "selected_sources": len(sources),
        "parsed_sources": sum(1 for source in sources if source.get("parse_status") == "complete"),
        "eligible_segments": len(segments),
        "term_records": sum(1 for _ in reader.iter("terms")),
        "decision_candidates": len(structured_parents) + sum(1 for claim in reader.iter("claims") if "decision" in [str(part).casefold() for part in (claim.get("qualifiers") or {}).get("scope", [])]),
        "decision_records": len(decisions),
        "warning_count": sum(1 for _ in reader.iter("warnings")),
        "ranking_rule_version": "scoring-v1",
        "decision_rule_version": "decision-rules-v1",
    }


def _coverage_diagnostics(coverage: Record) -> tuple[Record, ...]:
    diagnostics: tuple[Record, ...] = ()
    if coverage["decision_candidates"] and not coverage["decision_records"]:
        diagnostics = ({"code": "decision_reduction_empty", "message": "decision candidates were found but none reduced to decision records"},)
    return diagnostics


def _page(reader: SnapshotReader, records: Sequence[Record], **kwargs) -> QueryEnvelope:
    coverage = _coverage(reader)
    kwargs["binding"] = {**kwargs["binding"], "projection_version": 1, "ranking_version": "scoring-v1"}
    return page_records(records, coverage=coverage, diagnostics=_coverage_diagnostics(coverage), **kwargs)


def _catalog(reader: SnapshotReader) -> RecordCatalog:
    return RecordCatalog.from_records(record for record_type in RECORD_TYPES for record in reader.iter(record_type))


def _project_compact(records: list[Record], fields: Sequence[str] | None, command: str) -> list[Record]:
    if fields is None or not records:
        return records
    available = set().union(*(record.keys() for record in records))
    unavailable = sorted(set(fields) - available)
    if unavailable:
        raise ValueError(f"fields unavailable in compact {command} view: {', '.join(unavailable)}; use get, evidence, or explain for details")
    return [{field: record[field] for field in fields if field in record} for record in records]


def terms_query(reader: SnapshotReader, *, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    records = sorted((dict(x) for x in reader.iter("terms")), key=lambda x: (-float((rankings.get(str(x["id"]), {}).get("scores", {}).get("navigation") or {}).get("score", 0)), -float(x["tfidf"]), str(x["id"])))
    records = [summarize_record(record, rankings, evidence_limit=1) for record in records]
    for rank, record in enumerate(records, start=1):
        record["rank"] = rank
    records = _project_compact(records, fields, "terms")
    return _page(reader, records, binding={"snapshot_id": reader.snapshot_id, "command": "terms", "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def decisions_query(reader: SnapshotReader, *, score: str = "navigation", fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None, overlay_reader=None, base_only: bool = False) -> QueryEnvelope:
    if score not in {"navigation", "criticality", "review_priority", "extraction_confidence", "corroboration", "completeness"}: raise ValueError("invalid score")
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    resolutions = {} if overlay_reader is None or base_only else {str(x["decision_id"]): x for x in overlay_reader.iter_resolutions()}
    records = []
    for decision in reader.iter("decisions"):
        item = summarize_record(dict(decision), rankings)
        if overlay_reader is not None and not base_only:
            item = compose_decision_summary(item, resolutions.get(str(decision["id"])))
        records.append(item)
    records.sort(key=lambda x: (-float(x.get("scores", {}).get(score, 0)), str(x["id"])))
    records = _project_compact(records, fields, "decisions")
    return _page(reader, records, binding={"snapshot_id": reader.snapshot_id, "command": "decisions", "score": score, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def neighbors_query(reader: SnapshotReader, *, node_id: str, depth: int = 1, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    catalog = _catalog(reader)
    graph = GraphResult(tuple(r for r in catalog.all() if r["kind"] not in {"edge", "ranking"}), catalog.iter("edge"), catalog)
    result = bounded_neighbors(graph, node_id, depth, limit)
    records = [dict(item) for item in result.nodes]
    records = [{**summarize_record(item), "depth": item.get("depth")} for item in records]
    records = _project_compact(records, fields, "neighbors")
    return _page(reader, records, binding={"snapshot_id": reader.snapshot_id, "command": "neighbors", "node_id": node_id, "depth": depth, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def evidence_query(reader: SnapshotReader, *, record_id: str, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None) -> QueryEnvelope:
    catalog = _catalog(reader)
    record = catalog.maybe_get(record_id)
    if record is None and record_id.startswith("assertion:"):
        from architecture_graph.report import ReportLimits, build_report
        report = build_report(reader, limits=ReportLimits(max_chars=1_000_000))
        record = next((item for item in report.assertions if item["id"] == record_id), None)
    if record is None:
        raise KeyError(record_id)
    evidence_ids = list(record.get("evidence_ids", []))
    records = [dict(catalog.get(str(item))) for item in evidence_ids]
    return _page(reader, records, binding={"snapshot_id": reader.snapshot_id, "command": "evidence", "record_id": record_id, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=limit, max_chars=max_chars, cursor=cursor)


def explain_query(reader: SnapshotReader, *, record_id: str, fields: Sequence[str] | None = None, limit: int = 20, max_chars: int = 12_000, cursor: str | None = None, overlay_reader=None, base_only: bool = False) -> QueryEnvelope:
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
    if record.get("kind") == "decision" and overlay_reader is not None and not base_only:
        resolution = next((x for x in overlay_reader.iter_resolutions() if x.get("decision_id") == record_id), None)
        item["record_summary"] = compose_decision_summary(item["record_summary"], resolution)
    return _page(reader, [item], binding={"snapshot_id": reader.snapshot_id, "command": "explain", "record_id": record_id, "fields": fields, "limit": limit, "max_chars": max_chars}, fields=fields, limit=1, max_chars=max_chars, cursor=cursor)
