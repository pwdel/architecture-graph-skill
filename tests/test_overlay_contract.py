from pathlib import Path

from helpers.rationale_overlay import capture_frozen_base
from test_phase2_golden import _index


def test_repeated_index_preserves_frozen_base(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    before = capture_frozen_base(reader)
    after = capture_frozen_base(reader)
    assert after == before


def test_frozen_scoring_contract_remains_v1(tmp_path: Path) -> None:
    capture = capture_frozen_base(_index(tmp_path / "repo"))
    assert capture.semantic_schema == 2
    assert capture.scoring_rule_version == "scoring-v1"
