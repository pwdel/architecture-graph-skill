import json

from architecture_graph.capabilities import capability_record
from architecture_graph.cli import main


def test_capabilities_advertise_only_implemented_phase_two_commands() -> None:
    item = capability_record()
    assert item["phases"] == ["phase1", "phase2"]
    assert item["commands"] == [
        "capabilities",
        "decisions",
        "evidence",
        "explain",
        "find",
        "get",
        "index",
        "memory status",
        "neighbors",
        "report",
        "terms",
    ]
    assert item["unavailable"] == [
        "human_review_mutation",
        "image_interpretation",
        "semantic_snapshot_diff",
        "decision_lineage",
    ]


def test_capabilities_cli_returns_canonical_json(capsys) -> None:
    assert main(["capabilities", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "capability:phase2"
    assert payload["content_digest"].startswith("sha256:")
