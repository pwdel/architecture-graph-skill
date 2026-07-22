from pathlib import Path

from helpers.rationale_overlay import capture_frozen_base
from test_phase2_golden import _index
from architecture_graph.overlay_contract import validate_rationale_resolution


def test_repeated_index_preserves_frozen_base(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    before = capture_frozen_base(reader)
    after = capture_frozen_base(reader)
    assert after == before


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
