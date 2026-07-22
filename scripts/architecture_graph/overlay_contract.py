from __future__ import annotations

from collections.abc import Mapping, Sequence

from architecture_graph.schemas import ValidationIssue
from architecture_graph.snapshot import SnapshotReader


CLASSIFICATIONS = frozenset({"explicit", "recognized_alias", "ambiguous", "missing"})
OVERLAY_KINDS = frozenset({"rationale_resolution"})
OBSERVED_ROLES = frozenset(
    {"rationale", "context", "justification", "reason", "reasons", "why", "why_now"}
)


def validate_rationale_resolution(record: Mapping[str, object], base: SnapshotReader, overlay_derivation_ids: frozenset[str] = frozenset()) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    required = {"id", "kind", "schema_version", "base_snapshot_id", "decision_id", "decision_content_digest", "normalized_role", "observed_roles", "classification", "evidence_ids", "resolves_diagnostics", "rule_version", "rank_eligible", "derivation_ids"}
    for field in sorted(required - record.keys()):
        issues.append(ValidationIssue(field, "is required"))
    if issues:
        return tuple(issues)
    if record["kind"] != "rationale_resolution": issues.append(ValidationIssue("kind", "must be rationale_resolution"))
    if not isinstance(record["id"], str) or not record["id"].startswith("rationale-resolution:"): issues.append(ValidationIssue("id", "must be a rationale-resolution ID"))
    if record["schema_version"] != 1: issues.append(ValidationIssue("schema_version", "must be 1"))
    if record["base_snapshot_id"] != base.snapshot_id: issues.append(ValidationIssue("base_snapshot_id", "does not match base snapshot"))
    decision = base.get("decisions", str(record["decision_id"]))
    if decision is None: issues.append(ValidationIssue("decision_id", "does not resolve"))
    elif record["decision_content_digest"] != decision.get("content_digest"): issues.append(ValidationIssue("decision_content_digest", "does not match decision"))
    if record["normalized_role"] != "rationale": issues.append(ValidationIssue("normalized_role", "must be rationale"))
    classification = record["classification"]
    if classification not in CLASSIFICATIONS: issues.append(ValidationIssue("classification", "is unsupported"))
    if record["rule_version"] != "rationale-rules-v1": issues.append(ValidationIssue("rule_version", "is unsupported"))
    if record["rank_eligible"] is not False: issues.append(ValidationIssue("rank_eligible", "must be false"))
    for field in ("observed_roles", "evidence_ids", "resolves_diagnostics", "derivation_ids"):
        values = record[field]
        if not isinstance(values, list) or values != sorted(set(values)):
            issues.append(ValidationIssue(field, "must be canonically sorted and unique"))
    roles = record["observed_roles"] if isinstance(record["observed_roles"], list) else []
    evidence_ids = record["evidence_ids"] if isinstance(record["evidence_ids"], list) else []
    resolves = record["resolves_diagnostics"] if isinstance(record["resolves_diagnostics"], list) else []
    if any(role not in OBSERVED_ROLES for role in roles):
        issues.append(ValidationIssue("observed_roles", "contains an unsupported role"))
    if classification == "explicit" and ("rationale" not in roles or not evidence_ids):
        issues.append(ValidationIssue("classification", "explicit requires rationale evidence"))
    if classification == "recognized_alias" and (not roles or "rationale" in roles or not evidence_ids):
        issues.append(ValidationIssue("classification", "recognized_alias requires aliased evidence"))
    if classification == "ambiguous" and (not roles or not evidence_ids or resolves):
        issues.append(ValidationIssue("classification", "ambiguous requires unresolved evidence"))
    if classification == "missing" and (roles or evidence_ids or resolves):
        issues.append(ValidationIssue("classification", "missing cannot carry rationale evidence or resolutions"))
    if any(value != "missing_rationale" for value in resolves):
        issues.append(ValidationIssue("resolves_diagnostics", "can only resolve missing_rationale"))
    if resolves and (
        classification not in {"explicit", "recognized_alias"}
        or decision is None
        or "missing_rationale" not in decision.get("diagnostic_codes", [])
    ):
        issues.append(ValidationIssue("resolves_diagnostics", "does not match the base decision diagnostic"))
    decision_source_ids = set()
    if decision is not None:
        for decision_evidence_id in decision.get("evidence_ids", []):
            decision_evidence = base.get("evidence", str(decision_evidence_id))
            if decision_evidence is not None:
                decision_source_ids.add(str(decision_evidence["source_version_id"]))
    for evidence_id in record["evidence_ids"] if isinstance(record["evidence_ids"], list) else []:
        evidence = base.get("evidence", str(evidence_id))
        if evidence is None:
            issues.append(ValidationIssue("evidence_ids", f"missing reference: {evidence_id}"))
        elif str(evidence["source_version_id"]) not in decision_source_ids:
            issues.append(ValidationIssue("evidence_ids", f"is not decision-local: {evidence_id}"))
    for derivation_id in record["derivation_ids"] if isinstance(record["derivation_ids"], list) else []:
        if base.get("derivations", str(derivation_id)) is None and str(derivation_id) not in overlay_derivation_ids: issues.append(ValidationIssue("derivation_ids", f"missing reference: {derivation_id}"))
    return tuple(sorted(issues))


def validate_rationale_overlay(records: Sequence[Mapping[str, object]], base: SnapshotReader, overlay_derivations: Sequence[Mapping[str, object]] = ()) -> tuple[ValidationIssue, ...]:
    derivation_ids = frozenset(str(item["id"]) for item in overlay_derivations)
    issues: list[ValidationIssue] = []
    for record in records:
        if record.get("kind") not in OVERLAY_KINDS:
            issues.append(ValidationIssue("kind", "is not allowed in a rationale overlay"))
        issues.extend(validate_rationale_resolution(record, base, derivation_ids))
    decisions = [str(record.get("decision_id")) for record in records if "decision_id" in record]
    base_decisions = {str(record["id"]) for record in base.iter("decisions")}
    if len(decisions) != len(set(decisions)):
        issues.append(ValidationIssue("decision_id", "must have one resolution per decision"))
    if set(decisions) != base_decisions:
        issues.append(ValidationIssue("decision_id", "must resolve every base decision exactly once"))
    return tuple(sorted(issues))
