from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.records import Record
from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.snapshot import SnapshotReader


@dataclass(frozen=True)
class ReportLimits:
    section_items: int = 8

    @classmethod
    def defaults(cls) -> "ReportLimits": return cls()


@dataclass(frozen=True)
class ReportResult:
    assertions: tuple[Record, ...]
    sections: tuple[tuple[str, tuple[Record, ...]], ...]


def build_report(reader: SnapshotReader, *, limits: ReportLimits) -> ReportResult:
    from architecture_graph.semantic_queries import decisions_query, terms_query

    decisions = decisions_query(reader, score="criticality", limit=limits.section_items, max_chars=100_000).items
    terms = terms_query(reader, limit=limits.section_items, max_chars=100_000).items
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    nodes = {str(x["id"]): x for kind in ("terms", "entities", "claims", "decisions") for x in reader.iter(kind)}
    navigation_ids = sorted(rankings, key=lambda node_id: (-float(rankings[node_id]["scores"]["navigation"]["score"]), node_id))[:limits.section_items]
    navigation = tuple(nodes[node_id] for node_id in navigation_ids if node_id in nodes and nodes[node_id].get("evidence_ids"))
    review = tuple(item for item in decisions if "missing_rationale" in item.get("diagnostic_codes", []))
    evidence = {str(x["id"]): x for x in reader.iter("evidence")}
    sections = _hydrate_sections((navigation, decisions, review, terms), evidence)
    assertions = tuple(item for section in sections for item in section if item.get("evidence_ids"))
    return ReportResult(assertions, tuple(zip(("Navigation hubs", "Critical decisions and constraints", "Review priorities", "Glossary candidates"), sections, strict=True)))


def _hydrate_assertion(item: Record, evidence: dict[str, Record]) -> Record:
    citations = []
    for evidence_id in item.get("evidence_ids", []):
        source = evidence.get(str(evidence_id))
        if source:
            citations.append({"evidence_id": evidence_id, "path": source["path"], "span": source["span"], "text": source["text"]})
    item["citations"] = citations
    return item


def _hydrate_sections(sections, evidence: dict[str, Record]):
    return tuple(tuple(_hydrate_assertion(dict(item), evidence) for item in section) for section in sections)


def build_catalog_report(catalog: RecordCatalog, *, limits: ReportLimits) -> str:
    evidence = {str(x["id"]): x for x in catalog.iter("evidence")}
    rankings = {str(x["node_id"]): x for x in catalog.iter("ranking")}
    nodes = {str(x["id"]): x for kind in ("term", "entity", "claim", "decision") for x in catalog.iter(kind)}
    navigation_ids = sorted(rankings, key=lambda node_id: (-float(rankings[node_id]["scores"]["navigation"]["score"]), node_id))[:limits.section_items]
    navigation = tuple(nodes[node_id] for node_id in navigation_ids if node_id in nodes and nodes[node_id].get("evidence_ids"))
    decisions = tuple(sorted(catalog.iter("decision"), key=lambda x: (-float((rankings.get(str(x["id"]), {}).get("scores", {}).get("criticality") or {}).get("score", 0)), str(x["id"]))))[:limits.section_items]
    review = tuple(item for item in decisions if "missing_rationale" in item.get("diagnostic_codes", []))
    terms = tuple(sorted(catalog.iter("term"), key=lambda x: (-float(x["tfidf"]), str(x["id"]))))[:limits.section_items]
    sections = _hydrate_sections((navigation, decisions, review, terms), evidence)
    assertions = tuple(item for section in sections for item in section if item.get("evidence_ids"))
    return render_report_text(ReportResult(assertions, tuple(zip(("Navigation hubs", "Critical decisions and constraints", "Review priorities", "Glossary candidates"), sections, strict=True))))


def render_report_text(result: ReportResult) -> str:
    lines = ["# Architecture Graph Report", "", "## Coverage", ""]
    if not result.assertions: lines.extend(["No qualified claims were extracted.", ""])
    for title, items in result.sections:
        lines.extend([f"## {title}", ""])
        if not items:
            lines.extend(["- None found.", ""])
            continue
        for item in items:
            label = item.get("title") or item.get("name") or item.get("canonical_form") or item.get("id")
            citations = item.get("citations", [])
            citation = "; ".join(_render_citation(x) for x in citations) if citations else ", ".join(str(x) for x in item.get("evidence_ids", []))
            lines.append(f"- {label} [{citation}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_citation(citation: Record) -> str:
    span = citation["span"]
    end_column = "?" if span.get("end_column") is None else span["end_column"]
    return f"{citation['evidence_id']} {citation['path']}:{span['start_line']}:{span['start_column']}-{span['end_line']}:{end_column}"
