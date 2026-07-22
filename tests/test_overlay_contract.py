from pathlib import Path
import shutil

from helpers.rationale_overlay import capture_frozen_base
from test_phase2_golden import _index
from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.rationale_resolver import resolve_rationales
from architecture_graph.overlay_contract import (
    validate_rationale_overlay,
    validate_rationale_resolution,
)
import pytest
import json
from conftest import git, ignore_architecture_graph


def test_repeated_index_preserves_frozen_base(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    first = _index(repository)
    before = capture_frozen_base(first)
    shutil.rmtree(first.project.project_dir)
    indexed = index_corpus([repository], observed_at="2026-07-21T00:00:00Z")
    second = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    after = capture_frozen_base(second)
    assert after == before
    assert before.ranking_digest == "sha256:55ce33371eb200e6ffc82f7ecb02dc640f957f574c6c91fd0bbc51e81ce224dc"


def test_frozen_scoring_contract_remains_v1(tmp_path: Path) -> None:
    capture = capture_frozen_base(_index(tmp_path / "repo"))
    assert capture.semantic_schema == 2
    assert capture.scoring_rule_version == "scoring-v1"


def test_resolution_contract_rejects_ranking_and_stale_decision(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    record = next(item for item in resolve_rationales(reader).resolutions if item["classification"] != "missing")
    assert validate_rationale_resolution(record, reader, frozenset(record["derivation_ids"])) == ()
    assert validate_rationale_resolution({**record, "rank_eligible": True}, reader)
    assert validate_rationale_resolution({**record, "decision_content_digest": "sha256:" + "0" * 64}, reader)


def test_overlay_requires_exactly_one_resolution_for_every_decision(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    assert validate_rationale_overlay([], reader)


def test_overlay_rejects_base_semantic_record_kinds(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    decision = next(reader.iter("decisions"))
    issues = validate_rationale_overlay([decision], reader)
    assert any(issue.field == "kind" for issue in issues)


@pytest.mark.parametrize(
    "change",
    [
        {"classification": "explicit", "observed_roles": ["context"]},
        {"classification": "missing", "observed_roles": [], "resolves_diagnostics": [], "evidence_ids": ["keep"]},
        {"classification": "recognized_alias", "evidence_ids": []},
        {"resolves_diagnostics": ["missing_scope"]},
    ],
)
def test_resolution_rejects_inconsistent_classification_semantics(tmp_path: Path, change) -> None:
    reader = _index(tmp_path / "repo")
    record = next(item for item in resolve_rationales(reader).resolutions if item["classification"] != "missing")
    if change.get("evidence_ids") == ["keep"]:
        change = {**change, "evidence_ids": record["evidence_ids"]}
    assert validate_rationale_resolution({**record, **change}, reader)


def test_resolution_rejects_same_source_evidence_from_another_decision(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"decision_log": [
        {"decision": "Use adapters", "context": "Centralize contracts"},
        {"decision": "Use ports", "context": "Keep infrastructure replaceable"},
    ]}))
    git(architecture_repo, "add", "architecture/plan.json")
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(indexed.selection))
    resolutions = list(resolve_rationales(reader).resolutions)
    forged = {**resolutions[0], "evidence_ids": resolutions[1]["evidence_ids"]}
    issues = validate_rationale_resolution(forged, reader, frozenset(forged["derivation_ids"]))
    assert any(issue.field == "evidence_ids" and "decision-local" in issue.message for issue in issues)
