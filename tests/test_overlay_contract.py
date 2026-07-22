from pathlib import Path
import shutil

from helpers.rationale_overlay import capture_frozen_base
from test_phase2_golden import _index
from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.overlay_contract import (
    validate_rationale_overlay,
    validate_rationale_resolution,
)
import pytest


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
    decision = next(reader.iter("decisions"))
    evidence_id = decision["evidence_ids"][0]
    record = {
        "id": "rationale-resolution:test", "kind": "rationale_resolution",
        "schema_version": 1, "base_snapshot_id": reader.snapshot_id,
        "decision_id": decision["id"], "decision_content_digest": decision["content_digest"],
        "normalized_role": "rationale", "observed_roles": ["context"],
        "classification": "recognized_alias", "evidence_ids": [evidence_id],
        "resolves_diagnostics": ["missing_rationale"], "rule_version": "rationale-rules-v1",
        "rank_eligible": False, "derivation_ids": decision["derivation_ids"],
    }
    assert validate_rationale_resolution(record, reader) == ()
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
    decision = next(reader.iter("decisions"))
    record = {
        "id": "rationale-resolution:test", "kind": "rationale_resolution",
        "schema_version": 1, "base_snapshot_id": reader.snapshot_id,
        "decision_id": decision["id"], "decision_content_digest": decision["content_digest"],
        "normalized_role": "rationale", "observed_roles": ["context"],
        "classification": "recognized_alias", "evidence_ids": [decision["evidence_ids"][0]],
        "resolves_diagnostics": ["missing_rationale"], "rule_version": "rationale-rules-v1",
        "rank_eligible": False, "derivation_ids": decision["derivation_ids"],
    }
    if change.get("evidence_ids") == ["keep"]:
        change = {**change, "evidence_ids": record["evidence_ids"]}
    assert validate_rationale_resolution({**record, **change}, reader)
