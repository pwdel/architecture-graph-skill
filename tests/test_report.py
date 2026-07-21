from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.report import ReportLimits, build_report, render_report_text
from architecture_graph.snapshot import SnapshotReader
from conftest import ignore_architecture_graph
from architecture_graph.semantic_queries import evidence_query


def test_report_has_citable_architecture_sections(phase1_repository) -> None:
    ignore_architecture_graph(phase1_repository)
    result = index_corpus([phase1_repository])
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    report = build_report(reader, limits=ReportLimits.defaults())
    assert report.assertions
    assert all(item["evidence_ids"] for item in report.assertions)
    assert all(item["citations"] for item in report.assertions)
    assert all(item["citations"][0]["path"] and item["citations"][0]["span"]["start_line"] for item in report.assertions)
    text = render_report_text(report)
    assert "Navigation hubs" in text
    assert "Critical decisions and constraints" in text
    assert "Review priorities" in text


def test_report_bounds_citations_and_exposes_appendix_references(phase1_repository) -> None:
    ignore_architecture_graph(phase1_repository)
    result = index_corpus([phase1_repository])
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    report = build_report(reader, limits=ReportLimits(max_chars=3_000, citation_limit=2))
    text = render_report_text(report)
    assert len(text) <= 3_000
    assert all(len(item["citations"]) <= 2 for item in report.assertions)
    assert all(item["evidence_count"] >= len(item["citations"]) for item in report.assertions)
    assert all(item["appendix_record_id"] == item["id"] for item in report.assertions)
    appendix = evidence_query(reader, record_id=report.assertions[0]["id"], limit=1, max_chars=3_000)
    assert appendix.items
    assert appendix.items[0]["path"]
