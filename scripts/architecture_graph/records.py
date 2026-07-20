from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
from typing import TypeAlias

from architecture_graph.canonical import canonical_bytes, sha256_digest


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
Record: TypeAlias = dict[str, JSONValue]

RECORD_TYPES = (
    "sources",
    "segments",
    "terms",
    "entities",
    "claims",
    "decisions",
    "edges",
    "rankings",
    "derivations",
    "evidence",
    "proposals",
    "reviews",
    "lineage",
    "warnings",
)

RECORD_KIND_BY_TYPE = {
    "sources": "source",
    "segments": "segment",
    "terms": "term",
    "entities": "entity",
    "claims": "claim",
    "decisions": "decision",
    "edges": "edge",
    "rankings": "ranking",
    "derivations": "derivation",
    "evidence": "evidence",
    "proposals": "proposal",
    "reviews": "review",
    "lineage": "lineage",
    "warnings": "warning",
}

PHASE1_REQUIRED_FIELDS = {
    "source": frozenset(
        {
            "logical_source_id",
            "path",
            "source_kind",
            "document_role",
            "authority_class",
            "authority_basis",
            "tracked",
            "git_blob",
            "content_hash",
            "decodable",
            "adr_metadata",
            "adapter_name",
            "adapter_version",
            "parse_status",
            "warning_ids",
            "configuration_digest",
            "deterministic_pipeline_digest",
            "derivation_ids",
        }
    ),
    "segment": frozenset(
        {
            "source_version_id",
            "segment_kind",
            "heading_path",
            "ordinal",
            "text",
            "span",
            "metadata",
            "evidence_ids",
            "derivation_ids",
        }
    ),
    "evidence": frozenset(
        {
            "source_version_id",
            "segment_id",
            "path",
            "source_content_hash",
            "span",
            "text",
            "derivation_ids",
        }
    ),
    "derivation": frozenset(
        {
            "producer_kind",
            "method",
            "tool",
            "tool_version",
            "model",
            "model_version",
            "model_artifact_digest",
            "configuration_digest",
            "pipeline_digest",
            "input_ids",
            "output_kind",
            "output_identity_key",
            "created_at",
        }
    ),
    "warning": frozenset(
        {
            "code",
            "message",
            "source_version_id",
            "span",
            "possible_role",
            "derivation_ids",
        }
    ),
    "observation": frozenset(
        {
            "snapshot_id",
            "previous_current_snapshot_id",
            "base_deterministic_snapshot_id",
            "material_input_digest",
            "source_revision_digest",
            "branch",
            "commit",
            "dirty_fingerprint",
            "observed_at",
        }
    ),
}


@dataclass(frozen=True)
class SourceSpan:
    start_line: int
    end_line: int
    start_column: int = 1
    end_column: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.start_line) is not int
            or type(self.end_line) is not int
            or type(self.start_column) is not int
            or (
                self.end_column is not None
                and type(self.end_column) is not int
            )
        ):
            raise TypeError("source span coordinates must be integers or null")
        if self.start_line < 1 or self.end_line < 1 or self.start_column < 1:
            raise ValueError("source span coordinates must be positive")
        if self.end_line < self.start_line:
            raise ValueError("source span end is before start")
        if self.end_column is not None:
            if self.end_column < 1:
                raise ValueError("source span coordinates must be positive")
            if self.end_line == self.start_line and self.end_column <= self.start_column:
                raise ValueError("end_column is exclusive and must follow start_column")

    def as_record(self) -> Record:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_column": self.start_column,
            "end_column": self.end_column,
        }


def canonical_set(values: Iterable[str]) -> list[JSONValue]:
    return sorted(set(values))


def content_digest(record: Mapping[str, object]) -> str:
    content = {key: value for key, value in record.items() if key != "content_digest"}
    return sha256_digest(canonical_bytes(content))


def finalize_record(record: Mapping[str, object]) -> Record:
    finalized = dict(record)
    if not isinstance(finalized.get("id"), str) or not finalized["id"]:
        raise ValueError("record id is required")
    if not isinstance(finalized.get("kind"), str) or not finalized["kind"]:
        raise ValueError("record kind is required")
    finalized.pop("content_digest", None)
    finalized["content_digest"] = content_digest(finalized)
    return finalized  # type: ignore[return-value]


def validate_record(
    record: Mapping[str, object], expected_kind: str | None = None
) -> None:
    if not isinstance(record.get("id"), str) or not record["id"]:
        raise ValueError("record id is required")
    if not isinstance(record.get("kind"), str) or not record["kind"]:
        raise ValueError("record kind is required")
    if expected_kind is not None and record["kind"] != expected_kind:
        raise ValueError(f"expected {expected_kind}, got {record['kind']}")
    if record.get("content_digest") != content_digest(record):
        raise ValueError(f"content digest mismatch for {record['id']}")


def validate_record_shape(record: Mapping[str, object]) -> None:
    kind = str(record.get("kind", ""))
    required = PHASE1_REQUIRED_FIELDS.get(kind)
    if required is None:
        return
    missing = sorted(required - record.keys())
    if missing:
        raise ValueError(f"{kind} record is missing fields: {', '.join(missing)}")

    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id.startswith(f"{kind}:"):
        raise ValueError(f"{kind} ID must start with {kind}:")

    def require_string(field: str, *, nullable: bool = False) -> str | None:
        value = record[field]
        if value is None and nullable:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f"{kind}.{field} must be a non-empty string")
        return value

    def require_digest(field: str, *, nullable: bool = False) -> None:
        value = require_string(field, nullable=nullable)
        if value is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError(f"{kind}.{field} must be a sha256 digest")

    def require_id(field: str, prefix: str, *, nullable: bool = False) -> None:
        value = require_string(field, nullable=nullable)
        if value is not None and not value.startswith(f"{prefix}:"):
            raise ValueError(f"{kind}.{field} must reference {prefix}")

    def require_ids(
        field: str, prefix: str | None = None, *, allow_empty: bool = True
    ) -> None:
        value = record[field]
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise ValueError(f"{kind}.{field} must be a string list")
        if not allow_empty and not value:
            raise ValueError(f"{kind}.{field} must be non-empty")
        if value != sorted(set(value)):
            raise ValueError(f"{kind}.{field} must be sorted and unique")
        if prefix is not None and any(
            not item.startswith(f"{prefix}:") for item in value
        ):
            raise ValueError(f"{kind}.{field} must reference {prefix}")

    def require_span(field: str, *, nullable: bool = False) -> None:
        value = record[field]
        if value is None and nullable:
            return
        if not isinstance(value, Mapping):
            raise ValueError(f"{kind}.{field} must be a source span")
        try:
            span = SourceSpan(
                start_line=value["start_line"],
                end_line=value["end_line"],
                start_column=value["start_column"],
                end_column=value["end_column"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{kind}.{field} is invalid: {error}") from error
        if span.as_record() != dict(value):
            raise ValueError(f"{kind}.{field} has unknown fields")

    if kind == "source":
        require_id("logical_source_id", "logical-source")
        require_string("path")
        if record["source_kind"] not in {"markdown", "mermaid", "plantuml", "yaml", "json", "text"}:
            raise ValueError("source.source_kind is invalid")
        require_string("document_role")
        if record["authority_class"] not in {
            "accepted_adr_or_active_standard",
            "approved_policy_or_constraint",
            "maintained_architecture",
            "narrative_note",
            "proposal_or_draft",
        }:
            raise ValueError("source.authority_class is invalid")
        require_string("authority_basis")
        if type(record["tracked"]) is not bool or type(record["decodable"]) is not bool:
            raise ValueError("source tracked/decodable fields must be booleans")
        require_string("git_blob", nullable=True)
        require_digest("content_hash")
        if not isinstance(record["adr_metadata"], Mapping):
            raise ValueError("source.adr_metadata must be an object")
        require_string("adapter_name")
        require_string("adapter_version")
        if record["parse_status"] not in {"complete", "partial", "failed"}:
            raise ValueError("source.parse_status is invalid")
        require_ids("warning_ids", "warning")
        require_digest("configuration_digest")
        require_digest("deterministic_pipeline_digest")
        require_ids("derivation_ids", "derivation", allow_empty=False)
    elif kind == "segment":
        require_id("source_version_id", "source")
        require_string("segment_kind")
        if not isinstance(record["heading_path"], list) or any(
            not isinstance(item, str) for item in record["heading_path"]
        ):
            raise ValueError("segment.heading_path must be a string list")
        if type(record["ordinal"]) is not int or record["ordinal"] < 0:
            raise ValueError("segment.ordinal must be a nonnegative integer")
        require_string("text")
        require_span("span")
        if not isinstance(record["metadata"], Mapping):
            raise ValueError("segment.metadata must be an object")
        require_ids("evidence_ids", "evidence", allow_empty=False)
        require_ids("derivation_ids", "derivation", allow_empty=False)
    elif kind == "evidence":
        require_id("source_version_id", "source")
        require_id("segment_id", "segment")
        require_string("path")
        require_digest("source_content_hash")
        require_span("span")
        require_string("text")
        require_ids("derivation_ids", "derivation", allow_empty=False)
    elif kind == "derivation":
        if record["producer_kind"] not in {"deterministic", "llm", "human"}:
            raise ValueError("derivation.producer_kind is invalid")
        for field in ("method", "tool", "tool_version", "output_kind", "output_identity_key"):
            require_string(field)
        for field in ("model", "model_version"):
            require_string(field, nullable=True)
        require_digest("model_artifact_digest", nullable=True)
        require_digest("configuration_digest")
        require_digest("pipeline_digest")
        require_ids("input_ids", allow_empty=False)
        created_at = record["created_at"]
        if record["producer_kind"] == "deterministic" and created_at is not None:
            raise ValueError("deterministic derivation.created_at must be null")
        if record["producer_kind"] != "deterministic" and not isinstance(created_at, str):
            raise ValueError("event derivation.created_at must be a string")
    elif kind == "warning":
        require_string("code")
        require_string("message")
        require_id("source_version_id", "source", nullable=True)
        require_span("span", nullable=True)
        require_string("possible_role", nullable=True)
        require_ids("derivation_ids", "derivation", allow_empty=False)
    elif kind == "observation":
        require_string("snapshot_id")
        require_string("previous_current_snapshot_id", nullable=True)
        require_string("base_deterministic_snapshot_id", nullable=True)
        require_digest("material_input_digest")
        require_digest("source_revision_digest")
        require_string("branch", nullable=True)
        require_string("commit", nullable=True)
        require_digest("dirty_fingerprint")
        require_string("observed_at")
