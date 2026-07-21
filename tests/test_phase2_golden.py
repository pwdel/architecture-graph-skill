from pathlib import Path
import shutil
import subprocess

from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.report import ReportLimits, build_report, render_report_text
from architecture_graph.snapshot import SnapshotReader


FIXTURE = Path(__file__).parent / "fixtures" / "phase2_repo"


def _index(destination: Path, *, duplicate: bool = True) -> SnapshotReader:
    shutil.copytree(FIXTURE, destination)
    if not duplicate:
        (destination / "architecture" / "duplicate-overview.md").unlink()
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
    assert any(item["code"] == "unmatched_relation" for item in reader.iter("warnings"))


def test_duplicate_bytes_do_not_inflate_semantic_features_or_scores(tmp_path) -> None:
    single = _index(tmp_path / "single", duplicate=False)
    copied = _index(tmp_path / "copied", duplicate=True)
    single_terms = {x["canonical_form"]: (x["tfidf"], x["distinct_source_count"]) for x in single.iter("terms")}
    copied_terms = {x["canonical_form"]: (x["tfidf"], x["distinct_source_count"]) for x in copied.iter("terms")}
    assert single_terms == copied_terms
    single_claims = {(x["subject"]["surface"], x["predicate"], x["object"]["surface"]) for x in single.iter("claims")}
    copied_claims = {(x["subject"]["surface"], x["predicate"], x["object"]["surface"]) for x in copied.iter("claims")}
    assert single_claims == copied_claims
    single_term_scores = {x["canonical_form"]: next(r["scores"] for r in single.iter("rankings") if r["node_id"] == x["id"]) for x in single.iter("terms")}
    copied_term_scores = {x["canonical_form"]: next(r["scores"] for r in copied.iter("rankings") if r["node_id"] == x["id"]) for x in copied.iter("terms")}
    assert single_term_scores == copied_term_scores


def test_diagram_claims_use_real_endpoints(tmp_path) -> None:
    reader = _index(tmp_path / "repo")
    diagram = {(x["subject"]["surface"], x["predicate"], x["object"]["surface"]) for x in reader.iter("claims") if x["parser_provenance"] == "diagram_edge"}
    assert ("Frontend", "routes_to", "Gateway") in diagram
    assert ("Gateway", "routes_to", "Checkout") in diagram


def test_semantic_derivations_use_active_snapshot_identity(tmp_path) -> None:
    reader = _index(tmp_path / "repo")
    derivation = next(x for x in reader.iter("derivations") if x["method"] == "sparse_tfidf")
    assert derivation["tool_version"] == "0.3.0"
    assert derivation["configuration_digest"] == reader.manifest["configuration_digest"]
    assert derivation["pipeline_digest"] == reader.manifest["deterministic_pipeline_digest"]
