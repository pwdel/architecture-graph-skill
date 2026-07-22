from __future__ import annotations

from collections import Counter, defaultdict

from architecture_graph import __version__
from architecture_graph.analysis_types import analysis_identity, build_analysis_derivation
from architecture_graph.canonical import stable_id
from architecture_graph.overlay_types import RationaleCoverage, RationaleOverlayResult
from architecture_graph.rationale_rules import load_rationale_rules, rationale_rule_digest
from architecture_graph.records import Record, finalize_record
from architecture_graph.snapshot import SnapshotReader


def eligible_rationale_evidence_ids(base: SnapshotReader, decision: Record) -> frozenset[str]:
    rules = load_rationale_rules()
    aliases = set(rules["aliases"])
    sources = {
        str(evidence["source_version_id"])
        for evidence_id in decision.get("evidence_ids", [])
        if (evidence := base.get("evidence", str(evidence_id))) is not None
    }
    scope = tuple(str(value) for value in decision.get("scope", []))
    parent = "/" + "/".join(scope) if scope else ""
    prose_owner = scope[:-1] if scope and scope[-1].casefold() == "decision" else scope
    eligible = {str(value) for value in decision.get("rationale_evidence_ids", [])}
    for segment in base.iter("segments"):
        if str(segment.get("source_version_id")) not in sources:
            continue
        metadata = segment.get("metadata", {})
        pointer = metadata.get("json_pointer") if isinstance(metadata, dict) else None
        if isinstance(pointer, str) and "/" in pointer:
            candidate_parent, role = pointer.rsplit("/", 1)
            if candidate_parent == parent and role in aliases:
                eligible.update(str(value) for value in segment.get("evidence_ids", []))
        heading_path = segment.get("heading_path", [])
        if (
            decision.get("anchor_kind") == "decision_heading"
            and isinstance(heading_path, list)
            and heading_path
            and tuple(str(value) for value in heading_path[:-1]) == prose_owner
            and str(heading_path[-1]).strip().casefold() in aliases
            and segment.get("segment_kind") not in {"heading", "metadata_field"}
        ):
            eligible.update(str(value) for value in segment.get("evidence_ids", []))
    return frozenset(eligible)


def resolve_rationales(base: SnapshotReader) -> RationaleOverlayResult:
    rules = load_rationale_rules()
    aliases = dict(rules["aliases"])
    structured: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    prose: dict[tuple[str, tuple[str, ...]], list[tuple[str, str, str]]] = defaultdict(list)
    for segment in base.iter("segments"):
        metadata = segment.get("metadata", {})
        pointer = metadata.get("json_pointer") if isinstance(metadata, dict) else None
        if isinstance(pointer, str) and "/" in pointer:
            parent, role = pointer.rsplit("/", 1)
            if role in aliases:
                for evidence_id in segment.get("evidence_ids", []):
                    source_id = str(segment["source_version_id"])
                    structured[(source_id, parent)].append(
                        (role, str(evidence_id), f"structured:{source_id}:{parent}")
                    )
        heading_path = segment.get("heading_path", [])
        if (
            isinstance(heading_path, list)
            and heading_path
            and str(heading_path[-1]).strip().casefold() in aliases
            and segment.get("segment_kind") not in {"heading", "metadata_field"}
        ):
            role = str(heading_path[-1]).strip().casefold()
            source_id = str(segment["source_version_id"])
            owner_path = tuple(str(value) for value in heading_path[:-1])
            for evidence_id in segment.get("evidence_ids", []):
                prose[(source_id, owner_path)].append(
                    (role, str(evidence_id), f"prose:{source_id}:{'/'.join(owner_path)}")
                )
    decisions = list(base.iter("decisions"))
    decision_sources: dict[str, set[str]] = {}
    for decision in decisions:
        source_ids = {
            str(evidence["source_version_id"])
            for evidence_id in decision.get("evidence_ids", [])
            if (evidence := base.get("evidence", str(evidence_id))) is not None
        }
        decision_sources[str(decision["id"])] = source_ids
    resolutions: list[Record] = []
    derivations: list[Record] = []
    counts: Counter[str] = Counter()
    for decision in decisions:
        scope = [str(value) for value in decision.get("scope", [])]
        parent = "/" + "/".join(scope) if scope else ""
        candidates: list[tuple[str, str, str]] = []
        for source_id in decision_sources[str(decision["id"])]:
            candidates.extend(structured.get((source_id, parent), []))
        candidates.extend(
            ("rationale", str(evidence_id), f"decision:{decision['id']}")
            for evidence_id in decision.get("rationale_evidence_ids", [])
        )
        if decision.get("anchor_kind") == "decision_heading":
            for source_id in decision_sources[str(decision["id"])]:
                owner_path = tuple(scope[:-1]) if scope and scope[-1].casefold() == "decision" else tuple(scope)
                candidates.extend(prose.get((source_id, owner_path), []))
        explicit_candidates = [item for item in candidates if item[0] == "rationale"]
        eligible = explicit_candidates or candidates
        roles = sorted({role for role, _, _ in eligible})
        evidence_ids = sorted({evidence for _, evidence, _ in eligible})
        candidate_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
        for role, evidence_id, scope_key in eligible:
            evidence = base.get("evidence", evidence_id)
            if evidence is not None:
                candidate_groups[(role, scope_key)].add(
                    " ".join(str(evidence.get("text", "")).casefold().split())
                )
        incompatible = len({tuple(sorted(values)) for values in candidate_groups.values()}) > 1
        if "rationale" in roles:
            classification = "ambiguous" if incompatible else "explicit"
        elif roles:
            classification = "ambiguous" if incompatible else "recognized_alias"
        else:
            classification = "missing"
        counts[classification] += 1
        with analysis_identity(
            __version__,
            str(base.manifest["configuration_digest"]),
            rationale_rule_digest(),
        ):
            derivation = build_analysis_derivation("rationale_rules_v1", evidence_ids or [str(decision["id"])], "rationale_resolution", str(decision["id"]))
        derivations.append(derivation)
        resolves = ["missing_rationale"] if classification in {"explicit", "recognized_alias"} and "missing_rationale" in decision.get("diagnostic_codes", []) else []
        record_id = stable_id("rationale-resolution", base.snapshot_id, decision["id"], classification, roles, evidence_ids)
        resolutions.append(finalize_record({"id": record_id, "kind": "rationale_resolution", "schema_version": 1, "base_snapshot_id": base.snapshot_id, "decision_id": decision["id"], "decision_content_digest": decision["content_digest"], "normalized_role": "rationale", "observed_roles": roles, "classification": classification, "evidence_ids": evidence_ids, "resolves_diagnostics": resolves, "rule_version": "rationale-rules-v1", "rank_eligible": False, "derivation_ids": [derivation["id"]]}))
    coverage = RationaleCoverage(len(resolutions), counts["explicit"], counts["recognized_alias"], counts["ambiguous"], counts["missing"], 0)
    return RationaleOverlayResult(tuple(sorted(resolutions, key=lambda item: str(item["id"]))), tuple(sorted(derivations, key=lambda item: str(item["id"]))), (), coverage)
