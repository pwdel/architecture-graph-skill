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
    prose: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for segment in base.iter("segments"):
        metadata = segment.get("metadata", {})
        pointer = metadata.get("json_pointer") if isinstance(metadata, dict) else None
        if isinstance(pointer, str) and "/" in pointer:
            parent, role = pointer.rsplit("/", 1)
            if role in aliases:
                for evidence_id in segment.get("evidence_ids", []):
                    structured[parent].append((role, str(evidence_id)))
        heading_path = segment.get("heading_path", [])
        if (
            isinstance(heading_path, list)
            and heading_path
            and str(heading_path[-1]).strip().casefold() in aliases
            and segment.get("segment_kind") not in {"heading", "metadata_field"}
        ):
            role = str(heading_path[-1]).strip().casefold()
            for evidence_id in segment.get("evidence_ids", []):
                prose[str(segment["source_version_id"])].append((role, str(evidence_id)))
    decisions = list(base.iter("decisions"))
    decision_sources: dict[str, set[str]] = {}
    source_decision_counts: Counter[str] = Counter()
    for decision in decisions:
        source_ids = {
            str(evidence["source_version_id"])
            for evidence_id in decision.get("evidence_ids", [])
            if (evidence := base.get("evidence", str(evidence_id))) is not None
        }
        decision_sources[str(decision["id"])] = source_ids
        source_decision_counts.update(source_ids)
    resolutions: list[Record] = []
    derivations: list[Record] = []
    counts: Counter[str] = Counter()
    for decision in decisions:
        scope = [str(value) for value in decision.get("scope", [])]
        parent = "/" + "/".join(scope) if scope else ""
        candidates = list(structured.get(parent, []))
        candidates.extend(
            ("rationale", str(evidence_id))
            for evidence_id in decision.get("rationale_evidence_ids", [])
        )
        if decision.get("anchor_kind") == "decision_heading":
            for source_id in decision_sources[str(decision["id"])]:
                if source_decision_counts[source_id] == 1:
                    candidates.extend(prose.get(source_id, []))
        roles = sorted({role for role, _ in candidates})
        evidence_ids = sorted({evidence for _, evidence in candidates})
        if "rationale" in roles:
            classification = "explicit"
        elif roles:
            classification = "recognized_alias"
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
