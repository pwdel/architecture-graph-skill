from architecture_graph.overlay_queries import compose_decision_summary
from architecture_graph.semantic_queries import decisions_query
from test_phase2_golden import _index


def test_composition_resolves_active_diagnostic_without_mutating_base() -> None:
    base = {"id": "decision:one", "diagnostic_codes": ["missing_rationale", "missing_scope"]}
    resolution = {"classification": "recognized_alias", "observed_roles": ["context"], "evidence_ids": ["evidence:one"], "resolves_diagnostics": ["missing_rationale"], "rule_version": "rationale-rules-v1"}
    original = dict(base)
    composed = compose_decision_summary(base, resolution)
    assert composed["base_diagnostics"] == ["missing_rationale", "missing_scope"]
    assert composed["active_diagnostics"] == ["missing_scope"]
    assert composed["rationale_resolution"]["observed_roles"] == ["context"]
    assert base == original


def test_base_only_decisions_preserve_uncomposed_v031_shape(tmp_path) -> None:
    reader = _index(tmp_path / "repo")
    result = decisions_query(reader, base_only=True)
    assert result.items
    assert all("base_diagnostics" not in item for item in result.items)
    assert all("active_diagnostics" not in item for item in result.items)
