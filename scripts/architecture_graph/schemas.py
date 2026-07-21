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
    record_id = record.get("id")
    if kind in REQUIRED_FIELDS and (not isinstance(record_id, str) or not record_id.startswith(kind + ":")):
        issues.append(ValidationIssue("id", f"must start with {kind}:"))
    list_fields = {
        "term": ("observed_forms", "discovery_signals", "evidence_ids", "derivation_ids"),
        "entity": ("observed_forms", "evidence_ids", "derivation_ids"),
        "claim": ("evidence_ids", "derivation_ids"),
        "decision": ("scope", "claim_ids", "rationale_evidence_ids", "consequence_evidence_ids", "supporting_claim_ids", "contradicting_claim_ids", "diagnostic_codes", "evidence_ids", "derivation_ids"),
        "edge": ("evidence_ids", "derivation_ids", "source_content_hashes"),
        "ranking": ("eligible_content_hashes", "excluded_duplicate_paths", "evidence_ids", "derivation_ids"),
    }
    for field in list_fields.get(kind, ()):
        value = record.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            issues.append(ValidationIssue(field, "must be a string list"))
        elif field != "scope" and value != sorted(set(value)):
            issues.append(ValidationIssue(field, "must be canonically sorted and unique"))
    for field in ("evidence_ids", "derivation_ids"):
        if field in REQUIRED_FIELDS.get(kind, ()) and isinstance(record.get(field), list) and not record[field] and not (kind == "ranking" and field == "evidence_ids"):
            issues.append(ValidationIssue(field, "must be non-empty"))
    if kind == "term":
        for field in ("canonical_form", "term_kind"):
            if not isinstance(record.get(field), str) or not record.get(field): issues.append(ValidationIssue(field, "must be a non-empty string"))
        for field in ("distinct_source_count", "document_frequency"):
            if type(record.get(field)) is not int or int(record[field]) < 1: issues.append(ValidationIssue(field, "must be a positive integer"))
        if not isinstance(record.get("tfidf"), (int, float)) or not math.isfinite(float(record.get("tfidf", 0))) or float(record.get("tfidf", 0)) < 0: issues.append(ValidationIssue("tfidf", "must be finite and non-negative"))
    if kind == "entity":
        for field in ("canonical_key", "name", "entity_type"):
            if not isinstance(record.get(field), str) or not record.get(field): issues.append(ValidationIssue(field, "must be a non-empty string"))
    if kind == "claim":
        for field in ("subject", "object"):
            argument = record.get(field)
            if not isinstance(argument, Mapping) or argument.get("kind") not in {"entity_ref", "literal"} or not isinstance(argument.get("surface"), str):
                issues.append(ValidationIssue(field, "must be a typed claim argument"))
            elif argument.get("kind") == "entity_ref" and (not isinstance(argument.get("entity_id"), str) or not str(argument.get("entity_id")).startswith("entity:")):
                issues.append(ValidationIssue(field + ".entity_id", "must reference an entity"))
        qualifiers = record.get("qualifiers")
        required_qualifiers = {"modality", "polarity", "conditions", "scope", "time_applicability", "applicability"}
        if not isinstance(qualifiers, Mapping) or not required_qualifiers <= qualifiers.keys():
            issues.append(ValidationIssue("qualifiers", "must contain all qualifier fields"))
        elif not isinstance(qualifiers.get("conditions"), list) or not isinstance(qualifiers.get("scope"), list):
            issues.append(ValidationIssue("qualifiers", "conditions and scope must be lists"))
        if record.get("tuple_complete") is not True: issues.append(ValidationIssue("tuple_complete", "must be true for a claim"))
        for field in ("predicate", "parser_provenance"):
            if not isinstance(record.get(field), str) or not record.get(field): issues.append(ValidationIssue(field, "must be a non-empty string"))
    if kind == "decision":
        for field in ("title", "status", "applicability"):
            if not isinstance(record.get(field), str) or not record.get(field): issues.append(ValidationIssue(field, "must be a non-empty string"))
    if kind == "edge" and record.get("edge_type") not in EDGE_TYPES:
        issues.append(ValidationIssue("edge_type", "is not a supported edge type"))
    if kind == "edge":
        for field in ("from_id", "to_id"):
            if not isinstance(record.get(field), str) or not record.get(field): issues.append(ValidationIssue(field, "must be a record ID"))
    if kind == "ranking" and isinstance(record.get("scores"), Mapping):
        scores = record["scores"]
        if set(scores) != SCORE_TYPES:
            issues.append(ValidationIssue("scores", "must contain four independent scores"))
        for name, payload in scores.items():
            value = payload.get("score") if isinstance(payload, Mapping) else None
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                issues.append(ValidationIssue(f"scores.{name}.score", "must be finite and between zero and one"))
            if not isinstance(payload, Mapping) or not isinstance(payload.get("features"), Mapping) or not isinstance(payload.get("rule_version"), str):
                issues.append(ValidationIssue(f"scores.{name}", "must contain features and rule version"))
            elif any(not isinstance(feature, str) or not isinstance(number, (int, float)) or not math.isfinite(float(number)) for feature, number in payload["features"].items()):
                issues.append(ValidationIssue(f"scores.{name}.features", "must contain finite numeric features"))
    elif kind == "ranking":
        issues.append(ValidationIssue("scores", "must be a mapping"))
    if kind == "ranking" and (not isinstance(record.get("node_id"), str) or not record.get("node_id")):
        issues.append(ValidationIssue("node_id", "must be a record ID"))
    if "content_digest" in record and record.get("content_digest") != content_digest(record):
        issues.append(ValidationIssue("content_digest", "does not match record content"))
    return tuple(sorted(issues))


def validate_snapshot_references(records_by_type: Mapping[str, Sequence[Record]]) -> tuple[ValidationIssue, ...]:
    records = [record for group in records_by_type.values() for record in group]
    ids = {str(record["id"]) for record in records}
    kinds = {str(record["id"]): str(record["kind"]) for record in records}
    issues: list[ValidationIssue] = []
    for record in records:
        for field in ("evidence_ids", "derivation_ids"):
            value = record.get(field, [])
            if not isinstance(value, list):
                issues.append(ValidationIssue(field, "must be a reference list"))
                continue
            for reference in value:
                if reference not in ids:
                    issues.append(ValidationIssue(field, f"missing reference {reference}"))
                elif kinds[reference] != ("evidence" if field == "evidence_ids" else "derivation"):
                    issues.append(ValidationIssue(field, f"reference {reference} has wrong kind {kinds[reference]}"))
        if record.get("kind") == "edge":
            for field in ("from_id", "to_id"):
                if record.get(field) not in ids:
                    issues.append(ValidationIssue(field, f"missing reference {record.get(field)}"))
                elif kinds[str(record.get(field))] not in NODE_TYPES:
                    issues.append(ValidationIssue(field, f"reference {record.get(field)} is not a graph node"))
        if record.get("kind") == "claim":
            for field in ("subject", "object"):
                argument = record.get(field)
                if isinstance(argument, Mapping) and argument.get("kind") == "entity_ref" and argument.get("entity_id") not in ids:
                    issues.append(ValidationIssue(field + ".entity_id", f"missing reference {argument.get('entity_id')}"))
                elif isinstance(argument, Mapping) and argument.get("kind") == "entity_ref" and kinds.get(str(argument.get("entity_id"))) != "entity":
                    issues.append(ValidationIssue(field + ".entity_id", f"reference {argument.get('entity_id')} is not an entity"))
        if record.get("kind") == "decision":
            for field in ("claim_ids", "rationale_evidence_ids", "consequence_evidence_ids", "supporting_claim_ids", "contradicting_claim_ids"):
                value = record.get(field, [])
                if not isinstance(value, list):
                    issues.append(ValidationIssue(field, "must be a reference list"))
                    continue
                for reference in value:
                    if reference not in ids:
                        issues.append(ValidationIssue(field, f"missing reference {reference}"))
                    else:
                        expected = "claim" if field in {"claim_ids", "supporting_claim_ids", "contradicting_claim_ids"} else "evidence"
                        if kinds[reference] != expected:
                            issues.append(ValidationIssue(field, f"reference {reference} has wrong kind {kinds[reference]}"))
        if record.get("kind") == "ranking" and record.get("node_id") not in ids:
            issues.append(ValidationIssue("node_id", f"missing reference {record.get('node_id')}"))
        elif record.get("kind") == "ranking" and kinds.get(str(record.get("node_id"))) not in NODE_TYPES:
            issues.append(ValidationIssue("node_id", f"reference {record.get('node_id')} is not a graph node"))
    return tuple(sorted(issues))
