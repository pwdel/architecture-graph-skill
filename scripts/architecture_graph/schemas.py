from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
import json
import math

from architecture_graph.canonical import canonical_bytes, sha256_digest
from architecture_graph.records import Record, content_digest


NODE_TYPES = frozenset({"source", "segment", "evidence", "term", "entity", "claim", "decision", "warning", "derivation"})
EDGE_TYPES = frozenset({"CONTAINS", "MENTIONS", "ASSERTS", "SUBJECT_OF", "OBJECT_OF", "SUPPORTS", "CONTRADICTS", "QUALIFIES", "DERIVED_FROM", "RELATED_TO"})
SCORE_TYPES = frozenset({"navigation", "criticality", "review_priority", "extraction_confidence"})

REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "term": frozenset({"canonical_form", "observed_forms", "term_kind", "distinct_source_count", "document_frequency", "tfidf", "discovery_signals", "evidence_ids", "derivation_ids"}),
    "entity": frozenset({"canonical_key", "name", "entity_type", "observed_forms", "evidence_ids", "derivation_ids"}),
    "claim": frozenset({"subject", "predicate", "object", "qualifiers", "tuple_complete", "parser_provenance", "evidence_ids", "derivation_ids"}),
    "decision": frozenset({"title", "status", "applicability", "scope", "claim_ids", "rationale_evidence_ids", "consequence_evidence_ids", "supporting_claim_ids", "contradicting_claim_ids", "diagnostic_codes", "evidence_ids", "derivation_ids"}),
    "edge": frozenset({"edge_type", "from_id", "to_id", "evidence_ids", "derivation_ids", "source_content_hashes"}),
    "ranking": frozenset({"node_id", "scores", "evidence_ids", "derivation_ids"}),
}


@dataclass(frozen=True, order=True)
class ValidationIssue:
    field: str
    message: str


def load_versioned_resource(name: str) -> Mapping[str, object]:
    if "/" in name or "\\" in name or not name.endswith(".json"):
        raise ValueError("invalid resource name")
    raw = files("architecture_graph.resources").joinpath(name).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"invalid versioned resource: {name}")
    return value


def resource_digest(name: str) -> str:
    return sha256_digest(canonical_bytes(load_versioned_resource(name)))


def validate_typed_record(record: Mapping[str, object], expected_kind: str | None = None) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    kind = record.get("kind")
    if expected_kind is not None and kind != expected_kind:
        issues.append(ValidationIssue("kind", f"expected {expected_kind}"))
    if not isinstance(kind, str):
        return tuple(sorted((*issues, ValidationIssue("kind", "must be a string"))))
    for field in sorted(REQUIRED_FIELDS.get(kind, frozenset()) - record.keys()):
        issues.append(ValidationIssue(field, "is required"))
    if kind == "edge" and record.get("edge_type") not in EDGE_TYPES:
        issues.append(ValidationIssue("edge_type", "is not a supported edge type"))
    if kind == "ranking" and isinstance(record.get("scores"), Mapping):
        scores = record["scores"]
        if set(scores) != SCORE_TYPES:
            issues.append(ValidationIssue("scores", "must contain four independent scores"))
        for name, payload in scores.items():
            value = payload.get("score") if isinstance(payload, Mapping) else None
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                issues.append(ValidationIssue(f"scores.{name}.score", "must be finite and between zero and one"))
    if "content_digest" in record and record.get("content_digest") != content_digest(record):
        issues.append(ValidationIssue("content_digest", "does not match record content"))
    return tuple(sorted(issues))


def validate_snapshot_references(records_by_type: Mapping[str, Sequence[Record]]) -> tuple[ValidationIssue, ...]:
    records = [record for group in records_by_type.values() for record in group]
    ids = {str(record["id"]) for record in records}
    issues: list[ValidationIssue] = []
    for record in records:
        for field in ("evidence_ids", "derivation_ids"):
            value = record.get(field, [])
            if isinstance(value, list):
                for reference in value:
                    if reference not in ids:
                        issues.append(ValidationIssue(field, f"missing reference {reference}"))
        if record.get("kind") == "edge":
            for field in ("from_id", "to_id"):
                if record.get(field) not in ids:
                    issues.append(ValidationIssue(field, f"missing reference {record.get(field)}"))
    return tuple(sorted(issues))
