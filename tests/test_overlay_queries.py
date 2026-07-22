from architecture_graph.overlay_queries import compose_decision_summary


def test_composition_resolves_active_diagnostic_without_mutating_base() -> None:
    base = {"id": "decision:one", "diagnostic_codes": ["missing_rationale", "missing_scope"]}
    resolution = {"classification": "recognized_alias", "observed_roles": ["context"], "evidence_ids": ["evidence:one"], "resolves_diagnostics": ["missing_rationale"], "rule_version": "rationale-rules-v1"}
    original = dict(base)
    composed = compose_decision_summary(base, resolution)
    assert composed["base_diagnostics"] == ["missing_rationale", "missing_scope"]
    assert composed["active_diagnostics"] == ["missing_scope"]
    assert composed["rationale_resolution"]["observed_roles"] == ["context"]
    assert base == original
