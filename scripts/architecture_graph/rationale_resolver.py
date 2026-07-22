from __future__ import annotations

from collections import Counter, defaultdict

from architecture_graph.analysis_types import build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.overlay_types import RationaleCoverage, RationaleOverlayResult
from architecture_graph.rationale_rules import load_rationale_rules
from architecture_graph.records import Record, finalize_record
from architecture_graph.snapshot import SnapshotReader


def resolve_rationales(base: SnapshotReader) -> RationaleOverlayResult:
    rules = load_rationale_rules()
    aliases = dict(rules["aliases"])
    structured: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for segment in base.iter("segments"):
        metadata = segment.get("metadata", {})
        pointer = metadata.get("json_pointer") if isinstance(metadata, dict) else None
        if not isinstance(pointer, str) or "/" not in pointer:
            continue
        parent, role = pointer.rsplit("/", 1)
        if role in aliases:
            for evidence_id in segment.get("evidence_ids", []):
                structured[parent].append((role, str(evidence_id)))
    resolutions: list[Record] = []
    derivations: list[Record] = []
    counts: Counter[str] = Counter()
    for decision in base.iter("decisions"):
        scope = [str(value) for value in decision.get("scope", [])]
        parent = "/" + "/".join(scope) if scope else ""
        candidates = structured.get(parent, [])
        roles = sorted({role for role, _ in candidates})
        evidence_ids = sorted({evidence for _, evidence in candidates})
        if "rationale" in roles:
            classification = "explicit"
        elif len(roles) == 1:
            classification = "recognized_alias"
        elif len(roles) > 1:
            classification = "ambiguous"
        else:
            classification = "missing"
        counts[classification] += 1
        derivation = build_analysis_derivation("rationale_rules_v1", evidence_ids or [str(decision["id"])], "rationale_resolution", str(decision["id"]))
        derivations.append(derivation)
        resolves = ["missing_rationale"] if classification in {"explicit", "recognized_alias"} and "missing_rationale" in decision.get("diagnostic_codes", []) else []
        record_id = stable_id("rationale-resolution", base.snapshot_id, decision["id"], classification, roles, evidence_ids)
        resolutions.append(finalize_record({"id": record_id, "kind": "rationale_resolution", "schema_version": 1, "base_snapshot_id": base.snapshot_id, "decision_id": decision["id"], "decision_content_digest": decision["content_digest"], "normalized_role": "rationale", "observed_roles": roles, "classification": classification, "evidence_ids": evidence_ids, "resolves_diagnostics": resolves, "rule_version": "rationale-rules-v1", "rank_eligible": False, "derivation_ids": [derivation["id"]]}))
    coverage = RationaleCoverage(len(resolutions), counts["explicit"], counts["recognized_alias"], counts["ambiguous"], counts["missing"], 0)
    return RationaleOverlayResult(tuple(sorted(resolutions, key=lambda item: str(item["id"]))), tuple(sorted(derivations, key=lambda item: str(item["id"]))), (), coverage)
