from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.report import ReportLimits, build_report, render_report_text
from architecture_graph.snapshot import SnapshotReader
from conftest import ignore_architecture_graph


def test_report_has_citable_architecture_sections(phase1_repository) -> None:
    ignore_architecture_graph(phase1_repository)
    result = index_corpus([phase1_repository])
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    report = build_report(reader, limits=ReportLimits.defaults())
    assert report.assertions
    assert all(item["evidence_ids"] for item in report.assertions)
    text = render_report_text(report)
    assert "Navigation hubs" in text
    assert "Critical decisions and constraints" in text
    assert "Review priorities" in text
