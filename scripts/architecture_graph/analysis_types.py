from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from architecture_graph.records import JSONValue, Record


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    segment_id: str
    source_version_id: str
    source_content_hash: str
    path: str
    text: str
    span: Mapping[str, JSONValue]
    format_kind: str
    segment_kind: str
    heading_path: tuple[str, ...] = ()
    section_role: str = "other"
    document_role: str = "architecture_note"
    authority_class: str = "informational"
    document_status: str = "unknown"
    adapter_name: str = "unknown"
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)
    derivation_id: str = ""


@dataclass(frozen=True)
class ParsedSentence:
    evidence_id: str
    text: str
    tokens: tuple[str, ...]
    noun_phrases: tuple[str, ...]
    acronyms: tuple[tuple[str, str], ...]
    format_kind: str
    section_role: str
    source_content_hash: str
    derivation_id: str
    unit: EvidenceUnit


@dataclass(frozen=True)
class RelationCandidate:
    subject: str | None
    predicate: str | None
    object: str | None
    evidence_id: str
    sentence: ParsedSentence
    parser_provenance: str
    tuple_complete: bool


@dataclass(frozen=True)
class QualifiedRelation:
    candidate: RelationCandidate
    modality: str = "asserted"
    polarity: str = "positive"
    conditions: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    time_applicability: str = "unspecified"
    applicability: str = "current"


@dataclass(frozen=True)
class ClaimArgument:
    kind: str
    surface: str
    entity_id: str | None = None
    value: JSONValue = None


@dataclass(frozen=True)
class RecordCatalog:
    _records: Mapping[str, Record]

    @classmethod
    def from_records(cls, records: Iterable[Record]) -> "RecordCatalog":
        indexed: dict[str, Record] = {}
        for record in records:
            record_id = str(record["id"])
            prior = indexed.get(record_id)
            if prior is not None and prior != record:
                raise ValueError("duplicate record id with different content")
            indexed[record_id] = record
        return cls(dict(sorted(indexed.items())))

    def add(self, records: Iterable[Record]) -> "RecordCatalog":
        return RecordCatalog.from_records((*self._records.values(), *records))

    def get(self, record_id: str) -> Record:
        return self._records[record_id]

    def maybe_get(self, record_id: str) -> Record | None:
        return self._records.get(record_id)

    def iter(self, kind: str) -> tuple[Record, ...]:
        return tuple(
            record for record in self._records.values() if record.get("kind") == kind
        )

    def all(self) -> tuple[Record, ...]:
        return tuple(self._records.values())

    def records_by_type(self) -> dict[str, tuple[Record, ...]]:
        result: dict[str, list[Record]] = {}
        for record in self._records.values():
            result.setdefault(str(record["kind"]) + "s", []).append(record)
        return {key: tuple(value) for key, value in sorted(result.items())}


@dataclass(frozen=True)
class AnalysisResult:
    catalog: RecordCatalog

    def records_by_type(self) -> dict[str, tuple[Record, ...]]:
        return self.catalog.records_by_type()
