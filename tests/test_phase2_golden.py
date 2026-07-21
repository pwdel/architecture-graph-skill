from pathlib import Path
import shutil
import subprocess

from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.report import ReportLimits, build_report, render_report_text
from architecture_graph.snapshot import SnapshotReader


FIXTURE = Path(__file__).parent / "fixtures" / "phase2_repo"


def _index(destination: Path) -> SnapshotReader:
    shutil.copytree(FIXTURE, destination)
    subprocess.run(["git", "-C", str(destination), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(destination), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(destination), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(destination), "add", "."], check=True)
    subprocess.run(["git", "-C", str(destination), "commit", "-m", "fixture"], check=True, capture_output=True)
    result = index_corpus([destination], observed_at="2026-07-21T00:00:00Z")
    return SnapshotReader.open(ProjectPaths.for_corpus(result.selection))


def _semantic(reader: SnapshotReader):
    return {kind: tuple(reader.iter(kind)) for kind in ("terms", "entities", "claims", "decisions", "edges", "rankings")}


def test_phase2_mixed_format_output_is_deterministic(tmp_path) -> None:
    assert _semantic(_index(tmp_path / "first")) == _semantic(_index(tmp_path / "second"))


def test_phase2_acceptance_contract(tmp_path) -> None:
    reader = _index(tmp_path / "repo")
    assert tuple(reader.iter("terms"))
    claims = tuple(reader.iter("claims"))
    assert {item["parser_provenance"] for item in claims} >= {"rule_prose", "diagram_edge"}
    rankings = tuple(reader.iter("rankings"))
    assert all(set(item["scores"]) == {"navigation", "criticality", "review_priority", "extraction_confidence"} for item in rankings)
    text = render_report_text(build_report(reader, limits=ReportLimits.defaults()))
    expected = (Path(__file__).parent / "fixtures" / "golden" / "phase2" / "report-headings.txt").read_text().splitlines()
    assert all(heading in text for heading in expected)
