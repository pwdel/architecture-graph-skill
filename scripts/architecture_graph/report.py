from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.records import Record
from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.canonical import stable_id


@dataclass(frozen=True)
class ReportLimits:
    section_items: int = 8
    max_chars: int = 12_000
    citation_limit: int = 2

    @classmethod
    def defaults(cls) -> "ReportLimits": return cls()


@dataclass(frozen=True)
class ReportResult:
    assertions: tuple[Record, ...]
    sections: tuple[tuple[str, tuple[Record, ...]], ...]
    coverage: Record


def build_report(reader: SnapshotReader, *, limits: ReportLimits, overlay_reader=None, base_only: bool = False) -> ReportResult:
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    nodes = {str(x["id"]): x for kind in ("terms", "entities", "claims", "decisions") for x in reader.iter(kind)}
    decisions = tuple(sorted(reader.iter("decisions"), key=lambda x: (-float((rankings.get(str(x["id"]), {}).get("scores", {}).get("criticality") or {}).get("score", 0)), str(x["id"]))))[:limits.section_items]
    if overlay_reader is not None and not base_only:
        from architecture_graph.overlay_queries import compose_decision_summary
        resolutions = {str(x["decision_id"]): x for x in overlay_reader.iter_resolutions()}
        decisions = tuple(compose_decision_summary(dict(item), resolutions.get(str(item["id"]))) for item in decisions)
    terms = tuple(sorted(reader.iter("terms"), key=lambda x: (-float(x["tfidf"]), str(x["id"]))))[:limits.section_items]
    navigation_ids = sorted(rankings, key=lambda node_id: (-float(rankings[node_id]["scores"]["navigation"]["score"]), node_id))[:limits.section_items]
    navigation = tuple(nodes[node_id] for node_id in navigation_ids if node_id in nodes and nodes[node_id].get("evidence_ids"))
    review = tuple(
        item
        for item in decisions
        if "missing_rationale"
        in item.get("active_diagnostics", item.get("diagnostic_codes", []))
    )
    evidence = {str(x["id"]): x for x in reader.iter("evidence")}
    titles = ("Navigation hubs", "Critical decisions and constraints", "Review priorities", "Glossary candidates")
    sections = _hydrate_sections((navigation, decisions, review, terms), evidence, titles, limits.citation_limit)
    from architecture_graph.semantic_queries import _coverage
    coverage = _coverage(reader)
    result = _report_result(titles, sections, coverage)
    mutable = [list(section) for section in sections]
    while len(render_report_text(result)) > limits.max_chars and any(mutable):
        for index in range(len(mutable) - 1, -1, -1):
            if mutable[index]:
                mutable[index].pop()
                break
        result = _report_result(titles, tuple(tuple(section) for section in mutable), coverage)
    if len(render_report_text(result)) > limits.max_chars:
        raise ValueError("report max_chars is too small for report headings")
    return result


def _hydrate_assertion(item: Record, evidence: dict[str, Record], section: str, citation_limit: int) -> Record:
    citations = []
    evidence_ids = [str(value) for value in item.get("evidence_ids", [])]
    for evidence_id in evidence_ids[:citation_limit]:
        source = evidence.get(str(evidence_id))
        if source:
            citations.append({"evidence_id": evidence_id, "path": source["path"], "span": source["span"], "text": source["text"]})
    label = item.get("title") or item.get("name") or item.get("canonical_form") or item.get("id")
    assertion_id = stable_id("assertion", section, item.get("id"), evidence_ids)
    result = {"id": assertion_id, "kind": "assertion", "subject_id": item.get("id"), "title": label, "section": section, "evidence_count": len(evidence_ids), "evidence_ids": evidence_ids, "citations": citations, "shown_evidence_ids": [citation["evidence_id"] for citation in citations], "appendix_record_id": assertion_id}
    if item.get("rationale_resolution"):
        result["rationale_resolution"] = item["rationale_resolution"]
    return result


def _hydrate_sections(sections, evidence: dict[str, Record], titles, citation_limit: int):
    return tuple(tuple(_hydrate_assertion(dict(item), evidence, title, citation_limit) for item in section if item.get("evidence_ids")) for title, section in zip(titles, sections, strict=True))


def _report_result(titles, sections, coverage: Record | None = None) -> ReportResult:
    assertions = tuple(item for section in sections for item in section)
    return ReportResult(assertions, tuple(zip(titles, sections, strict=True)), coverage or {})


def build_catalog_report(catalog: RecordCatalog, *, limits: ReportLimits) -> str:
    evidence = {str(x["id"]): x for x in catalog.iter("evidence")}
    rankings = {str(x["node_id"]): x for x in catalog.iter("ranking")}
    nodes = {str(x["id"]): x for kind in ("term", "entity", "claim", "decision") for x in catalog.iter(kind)}
    navigation_ids = sorted(rankings, key=lambda node_id: (-float(rankings[node_id]["scores"]["navigation"]["score"]), node_id))[:limits.section_items]
    navigation = tuple(nodes[node_id] for node_id in navigation_ids if node_id in nodes and nodes[node_id].get("evidence_ids"))
    decisions = tuple(sorted(catalog.iter("decision"), key=lambda x: (-float((rankings.get(str(x["id"]), {}).get("scores", {}).get("criticality") or {}).get("score", 0)), str(x["id"]))))[:limits.section_items]
    review = tuple(item for item in decisions if "missing_rationale" in item.get("diagnostic_codes", []))
    terms = tuple(sorted(catalog.iter("term"), key=lambda x: (-float(x["tfidf"]), str(x["id"]))))[:limits.section_items]
    titles = ("Navigation hubs", "Critical decisions and constraints", "Review priorities", "Glossary candidates")
    sections = _hydrate_sections((navigation, decisions, review, terms), evidence, titles, limits.citation_limit)
    return render_report_text(_report_result(titles, sections))


def render_report_text(result: ReportResult) -> str:
    lines = ["# Architecture Graph Report", "", "## Coverage", ""]
    if result.coverage:
        lines.extend([f"- Selected sources: {result.coverage['selected_sources']}", f"- Parsed sources: {result.coverage['parsed_sources']}", f"- Eligible segments: {result.coverage['eligible_segments']}", f"- Decisions: {result.coverage['decision_records']} from {result.coverage['decision_candidates']} candidates", ""])
    if not result.assertions: lines.extend(["No qualified claims were extracted.", ""])
    for title, items in result.sections:
        lines.extend([f"## {title}", ""])
        if not items:
            lines.extend(["- None found.", ""])
            continue
        for item in items:
            label = item.get("title") or item.get("id")
            citations = item.get("citations", [])
            citation = "; ".join(_render_citation(x) for x in citations) if citations else ", ".join(str(x) for x in item.get("evidence_ids", []))
            additional = int(item.get("evidence_count", 0)) - len(citations)
            suffix = f"; +{additional} additional; appendix {item['appendix_record_id']}" if additional > 0 else f"; appendix {item['appendix_record_id']}"
            lines.append(f"- {label} [{citation}{suffix}]")
            resolution = item.get("rationale_resolution")
            if resolution and resolution.get("classification") in {"explicit", "recognized_alias"}:
                roles = ", ".join(resolution.get("observed_roles", []))
                lines.append(f"  Rationale recognized through {roles}.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_citation(citation: Record) -> str:
    span = citation["span"]
    end_column = "?" if span.get("end_column") is None else span["end_column"]
    return f"{citation['evidence_id']} {citation['path']}:{span['start_line']}:{span['start_column']}-{span['end_line']}:{end_column}"
