from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.records import Record
from architecture_graph.semantic_queries import decisions_query, terms_query
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
    decisions = decisions_query(reader, score="criticality", limit=limits.section_items, max_chars=100_000).items
    terms = terms_query(reader, limit=limits.section_items, max_chars=100_000).items
    rankings = {str(x["node_id"]): x for x in reader.iter("rankings")}
    nodes = {str(x["id"]): x for kind in ("terms", "entities", "claims", "decisions") for x in reader.iter(kind)}
    navigation_ids = sorted(rankings, key=lambda node_id: (-float(rankings[node_id]["scores"]["navigation"]["score"]), node_id))[:limits.section_items]
    navigation = tuple(nodes[node_id] for node_id in navigation_ids if node_id in nodes and nodes[node_id].get("evidence_ids"))
    review = tuple(item for item in decisions if "missing_rationale" in item.get("diagnostic_codes", []))
    assertions = tuple(dict(item) for item in (*navigation, *decisions, *review, *terms) if item.get("evidence_ids"))
    return ReportResult(assertions, (("Navigation hubs", navigation), ("Critical decisions and constraints", decisions), ("Review priorities", review), ("Glossary candidates", terms)))


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
            evidence = ", ".join(str(x) for x in item.get("evidence_ids", []))
            lines.append(f"- {label} [{evidence}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
