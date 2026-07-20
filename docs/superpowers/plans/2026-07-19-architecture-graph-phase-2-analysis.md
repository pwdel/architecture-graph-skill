# Architecture Graph Phase 2 Deterministic Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 source-and-segment snapshot into an evidence-backed term dictionary, qualified relation and claim ledger, architecture decisions, typed graph, three independent rankings, engineer report, bounded context tools, and semantic snapshot diff without an LLM, database, or network call.

**Architecture:** Phase 1 JSONL remains the durable input and snapshot writer. Phase 2 builds deterministic in-memory stages in dependency order: pinned NLP runtime, TF-IDF term discovery, relation candidates, qualification, conservative normalization, claims, decisions, diagnostics, review projection, intrinsic features, semantic graph, history, structural ranking, report, and bounded queries. Every stage returns its records together with the exact deterministic derivation records those outputs cite; the indexer is still the sole publisher.

**Tech Stack:** uv-managed Python 3.12.13, Phase 1 JSON/JSONL storage, spaCy 3.8.x, scikit-learn 1.9.x, NetworkX 3.6.x, argparse, dataclasses, pytest 9.x.

## Global Constraints

- Phase 1 must pass from a clean checkout before this plan starts.
- JSON and JSONL remain the only durable stores. spaCy, scikit-learn, and NetworkX operate on ephemeral bounded in-memory projections.
- `index` never downloads a model, installs a package, calls a provider, or opens a network connection.
- A configured missing spaCy model emits a persisted `model_unavailable` warning and uses the English tokenizer plus explicit fallback rules. It never silently claims dependency-parse provenance.
- Unit tests construct real spaCy `Doc` objects programmatically and require no downloaded language model.
- No embeddings, vector database, pandas, OpenIE service, provider SDK, live LLM call, or `enrich` command enters Phase 2.
- Every derived record either directly references a persisted derivation or has a schema-defined provenance path to one. No derived record may cite an unpersisted derivation ID.
- Deterministic derivations have `created_at: null`; LLM and human event records retain event time.
- Producer kind, method, assertion kind, review status, source authority, decision status, extraction confidence, criticality, review priority, and confidence remain independent fields.
- Incomplete subject-predicate-object tuples remain candidates plus warnings and never enter `claims.jsonl`.
- Entity and decision merges use explicit identifiers, declared aliases, unambiguous acronyms, or exact canonical keys only. Similarity may emit `ALIAS_CANDIDATE`; it never merges records.
- Unaccepted proposals never become semantic assertions or current commitments.
- TF-IDF discovers and describes terms. It contributes only the approved five-percent lexical feature to criticality.
- Every `independent_source_count` uses distinct Phase 1 `source.content_hash` values. Copies of the same bytes at different paths may add mentions or evidence, but never increase term source counts, corroboration, evidence breadth, edge strength, status authority, persistence/churn positions, or rank features. Authority is reduced once per content-hash group to its least authoritative occurrence under the one versioned ordering; reducers and scorers never take a path-level maximum inside a duplicate group.
- All set-like values use canonical sorting; all scores are finite, clamped to zero through one, and rounded to eight places.
- A local source edit reruns every corpus-global stage before publication.
- Run every task test-first and commit only after its focused and cumulative tests pass.

## Checkpoints

1. Tasks 1–7: deterministic terms, qualified claims, and decisions.
2. Tasks 8–11: diagnostics, immutable review projection, intrinsic rankings, and the early engineer report.
3. Tasks 12–14: typed semantic graph, deterministic history, and final graph-backed rankings.
4. Tasks 15–18: bounded queries, context packs, semantic diff, and byte-level golden acceptance.

## File Map

### Analysis core

- `scripts/architecture_graph/analysis_types.py`: enums, immutable stage values, result objects, record catalog, and derivation builder.
- `scripts/architecture_graph/schemas.py`: required fields, identity/content boundaries, typed validation, and versioned resource loading.
- `scripts/architecture_graph/nlp.py`: no-download spaCy runtime, artifact identity, and parsed-segment corpus.
- `scripts/architecture_graph/terms.py`: deterministic candidates, sparse TF-IDF dictionary, and `TermIndex`.
- `scripts/architecture_graph/relations.py`: prose and diagram relation candidates.
- `scripts/architecture_graph/qualifiers.py`: modality, polarity, condition, scope, time, role, and applicability.
- `scripts/architecture_graph/ontology.py`: controlled architecture predicate vocabulary.
- `scripts/architecture_graph/entities.py`: conservative entity/literal resolution and alias candidates.
- `scripts/architecture_graph/claims.py`: canonical claim identity, invariants, provenance, and ledger materialization.
- `scripts/architecture_graph/decisions.py`: ordered source-anchor reducer and semantic decision digest.
- `scripts/architecture_graph/diagnostics.py`: conflicts and three-valued over-specification evaluation.
- `scripts/architecture_graph/reviews.py`: authority policy, stale-review handling, accepted proposals, and successors.
- `scripts/architecture_graph/projections.py`: lifecycle-lens and provenance-layer eligibility.
- `scripts/architecture_graph/features.py`: non-graph features and bounded retrieval documents.
- `scripts/architecture_graph/semantic_graph.py`: evidence graph and semantic ranking projection.
- `scripts/architecture_graph/history.py`: deterministic decision lineage, persistence, and churn.
- `scripts/architecture_graph/ranking.py`: intrinsic and structural scores with persisted derivations.
- `scripts/architecture_graph/report.py`: content-only engineer report.
- `scripts/architecture_graph/analysis.py`: stage orchestration and complete records-by-type result.

### Bounded retrieval

- `scripts/architecture_graph/paging.py`: limits, complete-item fitting, rendering, and bound cursors.
- `scripts/architecture_graph/decision_queries.py`: decisions, neighbors, evidence, explain, and report queries.
- `scripts/architecture_graph/context.py`: lexical seeding and typed bounded graph traversal.
- `scripts/architecture_graph/diff.py`: stable architecture-semantic snapshot changes.

### Versioned resources

- `scripts/architecture_graph/resources/__init__.py`
- `scripts/architecture_graph/resources/terms-en-v1.json`
- `scripts/architecture_graph/resources/predicates-v1.json`
- `scripts/architecture_graph/resources/extraction-rules-en-v1.json`
- `scripts/architecture_graph/resources/entity-rules-v1.json`
- `scripts/architecture_graph/resources/decision-rules-v1.json`
- `scripts/architecture_graph/resources/scoring-v1.json`
- `scripts/architecture_graph/resources/impact-rules-v1.json`
- `scripts/architecture_graph/resources/architect-questions-v1.json`

### Test support

- `tests/helpers/nlp_docs.py`: real programmatic spaCy documents.
- `tests/helpers/phase2_catalog.py`: real record catalogs, terms, diagnostics, and projections.
- `tests/helpers/history_snapshots.py`: immutable deterministic history fixtures.
- `tests/helpers/ranking_graphs.py`: semantic graph fixtures.
- `tests/helpers/query_snapshot.py`: published bounded-query snapshot.
- `tests/helpers/context_snapshot.py`: stored retrieval and traversal fixture.
- `tests/helpers/diff_snapshots.py`: V1/V2 semantic snapshot pair.
- `tests/fixtures/corpora/checkout-v1/` and `checkout-v2/`: adversarial architecture corpora.
- `tests/fixtures/reviews/`: proposal and human-review JSONL.
- `tests/fixtures/golden/checkout-v1/`: one manifest, fourteen JSONL files, and report.

---

### Task 1: Analysis Types, Typed Schemas, and Versioned Rules

**Files:**
- Modify: `scripts/architecture_graph/canonical.py`
- Modify: `scripts/architecture_graph/records.py`
- Create: `scripts/architecture_graph/analysis_types.py`
- Create: `scripts/architecture_graph/schemas.py`
- Create: `scripts/architecture_graph/resources/__init__.py`
- Create: `scripts/architecture_graph/resources/terms-en-v1.json`
- Create: `scripts/architecture_graph/resources/predicates-v1.json`
- Create: `scripts/architecture_graph/resources/extraction-rules-en-v1.json`
- Create: `scripts/architecture_graph/resources/entity-rules-v1.json`
- Create: `scripts/architecture_graph/resources/decision-rules-v1.json`
- Create: `scripts/architecture_graph/resources/architect-questions-v1.json`
- Modify: `pyproject.toml`
- Create: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_analysis_types.py`

**Interfaces:**
- Produces: `LifecycleLens`, `ProvenanceLayer`, `ExternalRecordRef`, `ClaimArgument`, `RelationCandidate`, `QualifiedRelation`, `IngestedCorpus`, and `RecordCatalog`.
- Produces immutable result types for every later stage, including `ReviewedMaterializationResult` for accepted-successor cascades.
- Produces: `canonical_utc_event_time(value: str) -> str` and `build_derivation_record(...) -> Record`; deterministic derivations require `created_at=None`, while `llm` and `human` derivations require the validated canonical UTC event form `YYYY-MM-DDTHH:MM:SSZ`.
- Produces: `load_versioned_resource(name: str) -> Mapping[str, object]` and `resource_digest(name: str) -> str`.
- Produces: `validate_typed_record(record, expected_kind=None) -> tuple[ValidationIssue, ...]`.
- Produces: `validate_snapshot_references(records_by_type, external_resolver) -> tuple[ValidationIssue, ...]`.

- [ ] **Step 1: Write failing union, catalog, derivation, schema, and resource tests**

Create `tests/test_analysis_types.py`:

```python
import pytest

from architecture_graph.analysis_types import (
    ClaimArgument,
    IngestedCorpus,
    LifecycleLens,
    ProvenanceLayer,
    RecordCatalog,
    ExternalRecordRef,
    build_derivation_record,
)
from architecture_graph.records import finalize_record
from architecture_graph.schemas import (
    SCHEMA_ENUMS,
    load_versioned_resource,
    resource_digest,
    validate_typed_record,
)
from tests.helpers.phase2_catalog import valid_typed_record


def test_claim_argument_requires_its_discriminated_payload() -> None:
    with pytest.raises(ValueError, match="entity_id"):
        ClaimArgument(kind="entity_ref", surface="Checkout", origin="explicit")
    literal = ClaimArgument(
        kind="literal",
        surface="30 days",
        origin="explicit",
        value=30,
        datatype="integer",
        unit="days",
    )
    assert literal.as_record()["unit"] == "days"
    with pytest.raises(ValueError, match="value"):
        ClaimArgument(
            kind="literal",
            surface="missing",
            origin="explicit",
            datatype="string",
        )
    null_literal = ClaimArgument(
        kind="literal",
        surface="null",
        origin="explicit",
        value=None,
        datatype="null",
    )
    assert "value" in null_literal.as_record()
    assert null_literal.as_record()["value"] is None
    with pytest.raises(ValueError, match="not allowed"):
        ClaimArgument(
            kind="entity_ref",
            surface="Checkout",
            origin="explicit",
            entity_id="entity:checkout",
            datatype="string",
        )


def test_catalog_rejects_same_id_with_different_content() -> None:
    first = finalize_record({"id": "claim:one", "kind": "claim", "value": 1})
    second = finalize_record({"id": "claim:one", "kind": "claim", "value": 2})
    with pytest.raises(ValueError, match="duplicate record id"):
        RecordCatalog.from_records([first, second])
    deduplicated = RecordCatalog.from_records([first, first])
    assert deduplicated.iter("claim") == (first,)


def test_derivation_keeps_producer_method_and_time_independent() -> None:
    record = build_derivation_record(
        producer_kind="deterministic",
        method="dependency_parse",
        tool="spacy",
        tool_version="3.8.14",
        model="fixture-en",
        model_version="1.0.0",
        model_artifact_digest="sha256:model",
        configuration_digest="sha256:config",
        pipeline_digest="sha256:pipeline",
        input_ids=("segment:one",),
        output_kind="relation_candidate_set",
        output_identity_key="segment:one",
        created_at=None,
        external_inputs=(
            ExternalRecordRef(
                snapshot_id="deterministic:" + "a" * 64,
                kind="decision",
                record_id="decision:prior",
                content_digest="sha256:" + "b" * 64,
            ),
        ),
    )
    assert record["producer_kind"] == "deterministic"
    assert record["method"] == "dependency_parse"
    assert record["created_at"] is None
    assert record["external_inputs"][0]["record_id"] == "decision:prior"


@pytest.mark.parametrize("producer_kind", ["llm", "human"])
def test_event_derivation_requires_canonical_utc_time(producer_kind: str) -> None:
    common = {
        "producer_kind": producer_kind,
        "method": "proposal_generation" if producer_kind == "llm" else "review_correction",
        "tool": "fixture",
        "tool_version": "1.0.0",
        "model": "fixture-model" if producer_kind == "llm" else None,
        "model_version": "1.0.0" if producer_kind == "llm" else None,
        "model_artifact_digest": "sha256:" + "1" * 64 if producer_kind == "llm" else None,
        "configuration_digest": "sha256:" + "2" * 64,
        "pipeline_digest": "sha256:" + "3" * 64,
        "input_ids": ("claim:one",),
        "output_kind": "proposal" if producer_kind == "llm" else "claim_successor",
        "output_identity_key": "claim:one",
    }
    with pytest.raises(ValueError, match="canonical UTC event time"):
        build_derivation_record(**common, created_at=None)
    with pytest.raises(ValueError, match="canonical UTC event time"):
        build_derivation_record(**common, created_at="2026-07-19T10:00:00+00:00")
    record = build_derivation_record(
        **common,
        created_at="2026-07-19T10:00:00Z",
    )
    assert record["created_at"] == "2026-07-19T10:00:00Z"
    invalid_payload = dict(record)
    invalid_payload.pop("content_digest")
    invalid_payload["created_at"] = "2026-07-19T10:00:00+00:00"
    invalid = finalize_record(invalid_payload)
    assert any(
        issue.field == "created_at"
        for issue in validate_typed_record(invalid, "derivation")
    )


def test_claim_schema_requires_every_qualified_claim_field() -> None:
    invalid = finalize_record({"id": "claim:one", "kind": "claim"})
    issues = validate_typed_record(invalid, "claim")
    assert [issue.field for issue in issues] == [
        "applicability",
        "assertion_kind",
        "claim_anchor",
        "claim_role",
        "decision_ids",
        "derivation_ids",
        "evidence_ids",
        "extraction_confidence",
        "field_origins",
        "object",
        "predicate",
        "qualifiers",
        "segment_id",
        "source_lineage",
        "source_version_ids",
        "subject",
    ]


def test_lenses_resources_and_corpus_order_are_stable() -> None:
    assert LifecycleLens.CURRENT.value == "current"
    assert ProvenanceLayer.REVIEWED.value == "reviewed"
    assert resource_digest("predicates-v1.json") == resource_digest(
        "predicates-v1.json"
    )
    source = finalize_record({"id": "source:one", "kind": "source"})
    segment_b = finalize_record(
        {"id": "segment:b", "kind": "segment", "source_version_id": "source:one", "text": "b"}
    )
    segment_a = finalize_record(
        {"id": "segment:a", "kind": "segment", "source_version_id": "source:one", "text": "a"}
    )
    corpus = IngestedCorpus.from_records([source], [segment_b, segment_a], [], [])
    assert [item["id"] for item in corpus.segments] == ["segment:a", "segment:b"]


def test_every_resource_value_is_declared_and_versioned() -> None:
    extraction = load_versioned_resource("extraction-rules-en-v1.json")
    decisions = load_versioned_resource("decision-rules-v1.json")
    assert set(extraction["modalities"]) == SCHEMA_ENUMS["modality"]
    assert set(extraction["polarities"]) == SCHEMA_ENUMS["polarity"]
    assert set(extraction["claim_roles"]) == SCHEMA_ENUMS["claim_role"]
    assert set(extraction["applicabilities"]) == SCHEMA_ENUMS["applicability"]
    assert set(decisions["decision_statuses"]) == SCHEMA_ENUMS["decision_status"]
    entities = load_versioned_resource("entity-rules-v1.json")
    assert set(entities["entity_types"]) == SCHEMA_ENUMS["entity_type"]
    predicates = load_versioned_resource("predicates-v1.json")
    surfaces = [
        surface
        for values in predicates["canonical_predicates"].values()
        for surface in values
    ]
    assert len(surfaces) == len(set(surfaces))


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("term", "term_kind"),
        ("claim", "assertion_kind"),
        ("proposal", "proposal_kind"),
        ("review", "verdict"),
        ("ranking", "ranking_phase"),
    ],
)
def test_unknown_variant_strings_fail_typed_validation(kind: str, field: str) -> None:
    record = valid_typed_record(kind)
    record[field] = "future-unknown-value"
    assert any(issue.field == field for issue in validate_typed_record(record, kind))
```

Run:

```bash
uv run pytest tests/test_analysis_types.py -q
```

Expected: FAIL because the analysis types, typed schemas, and resources do not exist.

- [ ] **Step 2: Add common enums, immutable values, result types, and derivations**

First extend `scripts/architecture_graph/canonical.py` with the shared event-time validator used by builders, Phase 1 record validation, review append, and typed snapshot validation:

```python
from datetime import datetime


_CANONICAL_UTC_EVENT_TIME = "%Y-%m-%dT%H:%M:%SZ"


def canonical_utc_event_time(value: str) -> str:
    try:
        parsed = datetime.strptime(value, _CANONICAL_UTC_EVENT_TIME)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "created_at must be a canonical UTC event time YYYY-MM-DDTHH:MM:SSZ"
        ) from error
    if parsed.strftime(_CANONICAL_UTC_EVENT_TIME) != value:
        raise ValueError(
            "created_at must be a canonical UTC event time YYYY-MM-DDTHH:MM:SSZ"
        )
    return value
```

In the Phase 1 `derivation` branch of `validate_record_shape`, retain the deterministic-null check and replace the non-deterministic string-only check with `canonical_utc_event_time(created_at)`. This is a strict extension of the repaired Phase 1 schema, not a second event-time implementation.

Create `scripts/architecture_graph/analysis_types.py` with these core contracts:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from collections.abc import Mapping, Sequence

from architecture_graph.canonical import canonical_utc_event_time, stable_id
from architecture_graph.records import JSONValue, Record, canonical_set, finalize_record


class LifecycleLens(StrEnum):
    CURRENT = "current"
    REVIEW = "review"
    HISTORICAL = "historical"


class ProvenanceLayer(StrEnum):
    DETERMINISTIC = "deterministic"
    ENRICHED = "enriched"
    REVIEWED = "reviewed"


_MISSING = object()


@dataclass(frozen=True, order=True)
class ExternalRecordRef:
    snapshot_id: str
    kind: str
    record_id: str
    content_digest: str

    def as_record(self) -> Mapping[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "kind": self.kind,
            "record_id": self.record_id,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class ClaimArgument:
    kind: str
    surface: str
    origin: str
    entity_id: str | None = None
    value: JSONValue | object = _MISSING
    datatype: str | None = None
    unit: str | None = None
    unresolved_text: str | None = None
    context_id: str | None = None

    def __post_init__(self) -> None:
        required = {
            "entity_ref": {"entity_id"},
            "literal": {"value", "datatype", "unit"},
            "unresolved_span": {"unresolved_text"},
            "implicit_context": {"context_id"},
        }
        if self.kind not in required:
            raise ValueError(f"unsupported claim argument kind: {self.kind}")
        payload = {
            "entity_id": self.entity_id,
            "value": self.value,
            "datatype": self.datatype,
            "unit": self.unit,
            "unresolved_text": self.unresolved_text,
            "context_id": self.context_id,
        }
        provided = {
            key for key, value in payload.items()
            if value is not None and value is not _MISSING
        }
        if self.kind == "literal" and self.value is not _MISSING:
            provided.add("value")
        extras = provided - required[self.kind]
        if extras:
            raise ValueError(
                f"payload fields not allowed for {self.kind}: {', '.join(sorted(extras))}"
            )
        must_have = {
            "entity_ref": {"entity_id"},
            "literal": {"value", "datatype"},
            "unresolved_span": {"unresolved_text"},
            "implicit_context": {"context_id"},
        }[self.kind]
        missing = must_have - provided
        if missing:
            raise ValueError(
                f"{', '.join(sorted(missing))} is required for {self.kind}"
            )

    def as_record(self) -> Record:
        result: Record = {
            "kind": self.kind,
            "surface": self.surface,
            "origin": self.origin,
        }
        for key, value in {
            "entity_id": self.entity_id,
            "datatype": self.datatype,
            "unit": self.unit,
            "unresolved_text": self.unresolved_text,
            "context_id": self.context_id,
        }.items():
            if value is not None:
                result[key] = value
        if self.kind == "literal":
            result["value"] = self.value
        return result


@dataclass(frozen=True)
class RelationCandidate:
    id: str
    segment_id: str
    source_version_id: str
    sentence_text: str
    subject_surface: str | None
    predicate_surface: str
    object_surface: str | None
    subject_origin: str
    object_origin: str
    evidence_ids: tuple[str, ...]
    derivation_ids: tuple[str, ...]
    confidence: float
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True)
class QualifiedRelation:
    candidate: RelationCandidate
    predicate_surface: str
    modality: str
    polarity: str
    conditions: tuple[str, ...]
    scope: Mapping[str, tuple[str, ...]]
    effective_time: Mapping[str, JSONValue]
    claim_role: str
    applicability: str
    extraction_confidence: float
    derivation_ids: tuple[str, ...]


@dataclass(frozen=True)
class IngestedCorpus:
    sources: tuple[Record, ...]
    segments: tuple[Record, ...]
    evidence: tuple[Record, ...]
    warnings: tuple[Record, ...]

    @classmethod
    def from_records(
        cls,
        sources: Sequence[Record],
        segments: Sequence[Record],
        evidence: Sequence[Record],
        warnings: Sequence[Record],
    ) -> "IngestedCorpus":
        ordered = lambda values: tuple(sorted(values, key=lambda item: str(item["id"])))
        return cls(ordered(sources), ordered(segments), ordered(evidence), ordered(warnings))

    def source(self, record_id: str) -> Record:
        return next(item for item in self.sources if item["id"] == record_id)

    def segment(self, record_id: str) -> Record:
        return next(item for item in self.segments if item["id"] == record_id)


@dataclass(frozen=True)
class RecordCatalog:
    records_by_kind: Mapping[str, tuple[Record, ...]]
    records_by_key: Mapping[tuple[str, str], Record]

    @classmethod
    def from_records(cls, records: Sequence[Record]) -> "RecordCatalog":
        by_key: dict[tuple[str, str], Record] = {}
        by_kind: dict[str, list[Record]] = {}
        for record in records:
            key = (str(record["kind"]), str(record["id"]))
            previous = by_key.get(key)
            if previous is not None and previous["content_digest"] != record["content_digest"]:
                raise ValueError(f"duplicate record id with different content: {key[1]}")
            if previous is not None:
                continue
            by_key[key] = record
            by_kind.setdefault(key[0], []).append(record)
        return cls(
            MappingProxyType(
                {
                    kind: tuple(sorted(values, key=lambda item: str(item["id"])))
                    for kind, values in by_kind.items()
                }
            ),
            MappingProxyType(by_key),
        )

    def get(self, kind: str, record_id: str) -> Record | None:
        return self.records_by_key.get((kind, record_id))

    def iter(self, kind: str) -> tuple[Record, ...]:
        return self.records_by_kind.get(kind, ())


@dataclass(frozen=True)
class TermIndex:
    by_id: Mapping[str, Record]
    by_normalized_kind: Mapping[tuple[str, str], Record]
    lexical_by_normalized: Mapping[str, Record]
    controlled_predicate_by_normalized: Mapping[str, Record]
    by_surface: Mapping[str, tuple[Record, ...]]
    by_vocabulary_index: Mapping[int, Record]
    idf: tuple[float, ...]
    normalizer_resource_digest: str


@dataclass(frozen=True)
class TermDiscoveryResult:
    terms: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class RelationCandidateResult:
    candidates: tuple[RelationCandidate, ...]
    claim_eligible_candidates: tuple[RelationCandidate, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class QualificationResult:
    relations: tuple[QualifiedRelation, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class EntityResolutionResult:
    entities: tuple[Record, ...]
    edges: tuple[Record, ...]
    arguments_by_candidate_id: Mapping[str, tuple[ClaimArgument, ClaimArgument]]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class ClaimMaterializationResult:
    claims: tuple[Record, ...]
    ontology_terms: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class DecisionReductionResult:
    decisions: tuple[Record, ...]
    updated_claims_by_id: Mapping[str, Record]
    edges: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class DiagnosticResult:
    conflict_edges: tuple[Record, ...]
    overspecification: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class ReviewProjection:
    status_by_target: Mapping[tuple[str, str], str]
    effective_status_by_target: Mapping[tuple[str, str], str]
    accepted_proposal_ids: tuple[str, ...]
    effective_review_ids: tuple[str, ...]
    stale_review_ids: tuple[str, ...]
    invalid_review_ids: tuple[str, ...]
    disputed_targets: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SuccessorMaterialization:
    records: tuple[Record, ...]
    lineage: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class ReviewedMaterializationResult:
    catalog: RecordCatalog
    claims: tuple[Record, ...]
    decisions: tuple[Record, ...]
    edges: tuple[Record, ...]
    diagnostics: DiagnosticResult
    lineage: tuple[Record, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class ReviewFinalizeResult:
    snapshot_id: str
    observation_id: str | None
    reused: bool


@dataclass(frozen=True)
class ProjectionSelection:
    lifecycle_lens: LifecycleLens
    provenance_layer: ProvenanceLayer
    records_by_kind: Mapping[str, tuple[Record, ...]]
    effective_status_by_target: Mapping[tuple[str, str], str]
    diagnostic_proposals: tuple[Record, ...]
    stale_review_ids: tuple[str, ...]
    invalid_review_ids: tuple[str, ...]
    disputed_targets: tuple[tuple[str, str], ...]

    def iter(self, kind: str) -> tuple[Record, ...]:
        return self.records_by_kind.get(kind, ())


@dataclass(frozen=True)
class RankingResult:
    rankings: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class GraphProjectionResult:
    evidence_graph: object
    projection: object
    persisted_edges: tuple[Record, ...]
    derivations: tuple[Record, ...]


@dataclass(frozen=True)
class HistoryResult:
    source_lineage: tuple[Record, ...]
    lineage: tuple[Record, ...]
    updated_decisions_by_id: Mapping[str, Record]
    history: object
    derivations: tuple[Record, ...]


def build_derivation_record(
    *,
    producer_kind: str,
    method: str,
    tool: str,
    tool_version: str,
    model: str | None,
    model_version: str | None,
    model_artifact_digest: str | None,
    configuration_digest: str,
    pipeline_digest: str,
    input_ids: tuple[str, ...],
    output_kind: str,
    output_identity_key: str,
    created_at: str | None,
    external_inputs: tuple[ExternalRecordRef, ...] = (),
) -> Record:
    if producer_kind == "deterministic":
        if created_at is not None:
            raise ValueError("deterministic derivations cannot contain created_at")
    elif producer_kind in {"llm", "human"}:
        if created_at is None:
            raise ValueError("event derivation requires a canonical UTC event time")
        created_at = canonical_utc_event_time(created_at)
    else:
        raise ValueError(f"unsupported producer kind: {producer_kind}")
    external_records = [item.as_record() for item in sorted(external_inputs)]
    derivation_id = stable_id(
        "derivation",
        producer_kind,
        method,
        tool,
        tool_version,
        model,
        model_version,
        model_artifact_digest,
        configuration_digest,
        pipeline_digest,
        canonical_set(input_ids),
        external_records,
        output_kind,
        output_identity_key,
    )
    return finalize_record(
        {
            "id": derivation_id,
            "kind": "derivation",
            "producer_kind": producer_kind,
            "method": method,
            "tool": tool,
            "tool_version": tool_version,
            "model": model,
            "model_version": model_version,
            "model_artifact_digest": model_artifact_digest,
            "configuration_digest": configuration_digest,
            "pipeline_digest": pipeline_digest,
            "input_ids": canonical_set(input_ids),
            "external_inputs": external_records,
            "output_kind": output_kind,
            "output_identity_key": output_identity_key,
            "created_at": created_at,
        }
)
```

Builder functions canonical-sort every tuple and wrap every mapping in `MappingProxyType` before constructing these frozen values. `GraphProjectionResult.evidence_graph` and `.projection`, and `HistoryResult.history`, are narrowed to the concrete frozen types introduced in Tasks 12 and 13. Every result containing derived durable records carries the exact persisted derivation records cited by those outputs.

- [ ] **Step 3: Add typed schemas and exact versioned resource loading**

Create `scripts/architecture_graph/schemas.py`. Define `REQUIRED_FIELDS` for `term`, `entity`, `claim`, `decision`, `edge`, `ranking`, `proposal`, `review`, and `lineage`; extend rather than replace Phase 1 validation. Declare identity fields explicitly:

```python
from collections.abc import Mapping
from typing import cast


SCHEMA_ENUMS = {
    "term_kind": frozenset(
        {
            "glossary",
            "acronym",
            "identifier",
            "heading_phrase",
            "named_entity",
            "noun_phrase",
            "ngram",
            "controlled_predicate",
        }
    ),
    "argument_kind": frozenset(
        {"entity_ref", "literal", "unresolved_span", "implicit_context"}
    ),
    "argument_origin": frozenset(
        {
            "explicit",
            "dependency_resolved",
            "coreference_resolved",
            "heading_context",
            "unresolved",
        }
    ),
    "entity_type": frozenset(
        {
            "component",
            "service",
            "data_store",
            "event",
            "interface",
            "shared_infrastructure",
            "concern",
            "consequence",
            "unknown",
        }
    ),
    "modality": frozenset(
        {"must", "should", "may", "planned", "indicative", "unknown"}
    ),
    "polarity": frozenset({"positive", "negative"}),
    "claim_role": frozenset(
        {
            "decision",
            "constraint",
            "option",
            "rationale",
            "consequence",
            "context",
            "observation",
        }
    ),
    "applicability": frozenset(
        {"active", "considered", "rejected", "contextual", "unknown"}
    ),
    "decision_status": frozenset(
        {"proposed", "accepted", "rejected", "deprecated", "superseded", "absent"}
    ),
    "status_resolution": frozenset({"resolved", "absent", "ambiguous"}),
    "assertion_kind": frozenset({"extracted", "inferred"}),
    "proposal_kind": frozenset(
        {
            "create_record",
            "replace_field",
            "add_alias",
            "merge_entities",
            "split_entity",
            "link_decision",
            "rewrite_report_text",
        }
    ),
    "verdict": frozenset(
        {
            "verify",
            "dispute",
            "reject",
            "accept_proposal",
            "reject_proposal",
            "correct",
        }
    ),
    "ranking_phase": frozenset({"intrinsic", "final"}),
    "lifecycle_lens": frozenset({"current", "review", "historical"}),
    "provenance_layer": frozenset({"deterministic", "enriched", "reviewed"}),
    "warning_scope": frozenset(
        {"analysis_source", "global", "decision_analysis", "decision_diagnostic"}
    ),
    "producer_kind": frozenset({"deterministic", "llm", "human"}),
}

REQUIRED_FIELDS = {
    "term": frozenset(
        {
            "normalized",
            "term_kind",
            "surface_forms",
            "vocabulary_index",
            "idf",
            "normalizer_resource_digest",
            "mention_count",
            "segment_count",
            "independent_source_count",
            "tfidf",
            "generic_hub",
            "evidence_ids",
            "derivation_ids",
        }
    ),
    "entity": frozenset(
        {
            "entity_type",
            "canonical_key",
            "declared_scope",
            "surface_forms",
            "evidence_ids",
            "derivation_ids",
            "field_origins",
        }
    ),
    "claim": frozenset(
        {
            "subject",
            "predicate",
            "object",
            "qualifiers",
            "claim_anchor",
            "claim_role",
            "applicability",
            "decision_ids",
            "assertion_kind",
            "extraction_confidence",
            "evidence_ids",
            "derivation_ids",
            "source_lineage",
            "source_version_ids",
            "segment_id",
            "field_origins",
        }
    ),
    "decision": frozenset(
        {
            "source_anchor",
            "source_anchor_aliases",
            "explicit_decision_ids",
            "logical_source_ids",
            "primary_canonical_claim_key",
            "canonical_claim_keys",
            "primary_claim_ids",
            "member_claim_ids",
            "decision_status",
            "status_resolution",
            "status_candidates",
            "status_evidence_ids",
            "source_version_ids",
            "derivation_ids",
            "predecessor_identity",
            "semantic_digest",
        }
    ),
    "edge": frozenset(
        {
            "edge_type",
            "from_id",
            "to_id",
            "normalized_scope",
            "effective_time",
            "edge_discriminator",
            "evidence_ids",
            "input_ids",
            "derivation_ids",
        }
    ),
    "ranking": frozenset(
        {
            "decision_id",
            "lifecycle_lens",
            "provenance_layer",
            "ranking_phase",
            "semantic_projection_digest",
            "scores",
            "ranks",
            "features",
            "retrieval",
            "input_ids",
            "derivation_ids",
        }
    ),
    "proposal": frozenset(
        {
            "target_kind",
            "target_id",
            "target_content_digest",
            "proposal_kind",
            "field_path",
            "proposed_value",
            "evidence_ids",
            "derivation_id",
        }
    ),
    "review": frozenset(
        {
            "target_kind",
            "target_id",
            "target_content_digest",
            "field_path",
            "verdict",
            "replacement_value",
            "evidence_ids",
            "reviewer_id",
            "reviewer_authority",
            "authority_policy_digest",
            "supersedes_review_id",
            "created_at",
        }
    ),
    "lineage": frozenset(
        {
            "predecessor_id",
            "predecessor_content_digest",
            "predecessor_snapshot_id",
            "successor_id",
            "successor_content_digest",
            "successor_snapshot_id",
            "reason",
            "input_ids",
            "derivation_ids",
        }
    ),
}

IDENTITY_FIELDS = {
    "term": ("/normalized", "/term_kind"),
    "entity": ("/entity_type", "/canonical_key", "/declared_scope"),
    "claim": (
        "/subject",
        "/predicate/canonical",
        "/object",
        "/qualifiers/scope",
        "/source_lineage",
        "/claim_anchor",
    ),
    "edge": (
        "/edge_type",
        "/from_id",
        "/to_id",
        "/normalized_scope",
        "/effective_time",
        "/edge_discriminator",
    ),
    "proposal": (
        "/derivation_id",
        "/target_kind",
        "/target_id",
        "/target_content_digest",
        "/proposal_kind",
        "/field_path",
        "/proposed_value",
    ),
    "review": (
        "/reviewer_id",
        "/target_kind",
        "/target_id",
        "/target_content_digest",
        "/field_path",
        "/verdict",
        "/replacement_value",
        "/evidence_ids",
        "/authority_policy_digest",
        "/supersedes_review_id",
        "/created_at",
    ),
}


def decision_identity_payload(decision: Mapping[str, object]) -> Mapping[str, object]:
    """Return the conditional canonical identity; never hash path provenance."""
    anchor = cast(Mapping[str, object], decision["source_anchor"])
    explicit_id = anchor.get("explicit_decision_id")
    if explicit_id is not None:
        return {
            "identity_kind": "explicit",
            "explicit_decision_id": explicit_id,
            "normalized_heading_anchor": anchor["normalized_heading_anchor"],
        }
    return {
        "identity_kind": "non_adr",
        "logical_source_id": anchor["logical_source_id"],
        "normalized_heading_anchor": anchor["normalized_heading_anchor"],
        "primary_canonical_claim_key": decision["primary_canonical_claim_key"],
    }


CORRECTABLE_FIELDS_VERSION = 1
CORRECTABLE_FIELDS_V1 = {
    "entity": frozenset(
        {"/entity_type", "/canonical_key", "/declared_scope"}
    ),
    "claim": frozenset(
        {
            "/subject/entity_id",
            "/subject/context_id",
            "/subject/value",
            "/predicate/canonical",
            "/object/entity_id",
            "/object/context_id",
            "/object/value",
            "/qualifiers/modality",
            "/qualifiers/polarity",
            "/qualifiers/conditions",
            "/qualifiers/scope",
            "/qualifiers/effective_time",
            "/claim_role",
            "/applicability",
        }
    ),
}
```

The `/subject` and `/object` claim entries name discriminated canonical selectors, not raw-object hashes. `argument_identity_payload` in Task 6 defines those selectors and excludes surface wording and extraction origin.

Decision identity is the output of `decision_identity_payload`, not a hash of the whole `source_anchor`. The explicit branch intentionally omits logical source and path so one explicit decision can be corroborated across sources. The non-ADR branch uses logical source, heading, and primary canonical claim key. Both branches exclude `relative_path`, source-version IDs, aliases, and evidence. Every stable-ID builder, review successor classifier, lineage matcher, and diff uses this selector.

`CORRECTABLE_FIELDS_V1` is the complete automated successor allowlist. V1 accepts direct `correct` reviews and accepted `replace_field` proposals only for those exact claim/entity pointers. Array-index pointers, envelope fields, provenance fields, and every ranking, decision, term, derivation, warning, review, or proposal field are diagnostic-only and cannot materialize a successor. Apply the replacement to a copy, revalidate the complete typed successor and all references, and append the proposal/review origins at the exact changed pointer. Entity and claim schemas therefore require `field_origins`; unsupported target kinds cannot bypass origin accounting. Expanding this table is a schema-versioned cascade change.

In the same module declare the publication reference contract:

```python
LOCAL_REFERENCE_FIELDS = {
    "term": ("/evidence_ids/*", "/derivation_ids/*"),
    "entity": (
        "/evidence_ids/*",
        "/derivation_ids/*",
        "/field_origins/*/*/id",
    ),
    "claim": (
        "/subject/entity_id",
        "/subject/context_id",
        "/object/entity_id",
        "/object/context_id",
        "/decision_ids/*",
        "/evidence_ids/*",
        "/derivation_ids/*",
        "/source_version_ids/*",
        "/segment_id",
        "/input_claim_ids/*",
        "/field_origins/*/*/id",
    ),
    "decision": (
        "/primary_claim_ids/*",
        "/member_claim_ids/*",
        "/status_evidence_ids/*",
        "/status_candidates/*/source_version_id",
        "/status_candidates/*/evidence_ids/*",
        "/source_version_ids/*",
        "/derivation_ids/*",
    ),
    "edge": (
        "/evidence_ids/*",
        "/input_ids/*",
        "/derivation_ids/*",
    ),
    "ranking": (
        "/decision_id",
        "/retrieval/evidence_ids/*",
        "/input_ids/*",
        "/derivation_ids/*",
    ),
    "proposal": ("/evidence_ids/*", "/derivation_id"),
    "review": ("/evidence_ids/*", "/supersedes_review_id"),
    "lineage": ("/input_ids/*", "/derivation_ids/*"),
    "warning": (
        "/source_version_id",
        "/decision_id",
        "/evidence_ids/*",
        "/input_ids/*",
        "/derivation_ids/*",
    ),
}

EDGE_ENDPOINT_KINDS = {
    "CLAIM_SUBJECT": ({"claim"}, {"entity"}),
    "CLAIM_PREDICATE": ({"claim"}, {"term"}),
    "CLAIM_OBJECT": ({"claim"}, {"entity"}),
    "BELONGS_TO_DECISION": ({"claim"}, {"decision"}),
    "EVIDENCED_BY": ({"claim", "decision", "entity", "term", "proposal", "review"}, {"evidence"}),
    "DERIVED_FROM": ({"claim", "decision", "entity", "term", "proposal"}, {"derivation"}),
    "SUPPORTS": ({"claim", "decision"}, {"claim", "decision"}),
    "CONTRADICTS": ({"claim", "decision"}, {"claim", "decision"}),
    "SUPERSEDES": ({"decision", "entity"}, {"decision", "entity"}),
    "ADDRESSES": ({"decision", "entity"}, {"entity"}),
    "JUSTIFIED_BY": ({"decision", "entity"}, {"claim", "entity"}),
    "GOVERNS": ({"decision"}, {"entity"}),
    "HAS_CONSEQUENCE": ({"decision"}, {"claim", "entity"}),
    "TRADES_OFF_WITH": ({"decision", "entity"}, {"claim", "entity"}),
    "CONSTRAINS": ({"claim", "decision", "entity"}, {"entity"}),
    "AFFECTS": ({"decision"}, {"entity"}),
    "ALIAS_CANDIDATE": ({"entity"}, {"entity"}),
    "PROPOSES": ({"proposal"}, {"claim", "decision", "entity", "term"}),
    "REVIEW_OF": (
        {"review"},
        {"proposal", "claim", "decision", "entity", "term", "derivation"},
    ),
    "CALLS": ({"entity"}, {"entity"}),
    "CAUSES": ({"entity"}, {"entity"}),
    "DEPENDS_ON": ({"entity"}, {"entity"}),
    "DEPLOYED_ON": ({"entity"}, {"entity"}),
    "OWNED_BY": ({"entity"}, {"entity"}),
    "PROHIBITS": ({"entity"}, {"entity"}),
    "PUBLISHES_TO": ({"entity"}, {"entity"}),
    "READS_FROM": ({"entity"}, {"entity"}),
    "REPLACES": ({"entity"}, {"entity"}),
    "REQUIRES": ({"entity"}, {"entity"}),
    "SUBSCRIBES_TO": ({"entity"}, {"entity"}),
    "WRITES_TO": ({"entity"}, {"entity"}),
}

WARNING_VARIANTS = {
    "source": frozenset(),
    "analysis_source": frozenset(
        {"warning_scope", "evidence_ids", "input_ids", "candidate_key"}
    ),
    "global": frozenset({"warning_scope"}),
    "decision_analysis": frozenset(
        {"warning_scope", "decision_id", "evidence_ids", "input_ids"}
    ),
    "decision_diagnostic": frozenset(
        {
            "warning_scope",
            "diagnostic_type",
            "decision_id",
            "result",
            "severity",
            "dimensions",
            "architect_question",
            "evidence_ids",
            "input_ids",
        }
    ),
}
```

`validate_snapshot_references(records_by_type, external_resolver)` walks only those declared pointers and treats null/absent optional pointers as empty. It also retains the Phase 1 checks for source, segment, evidence, warning, and derivation references. Claim subject/object `entity_id` references are required only for `entity_ref`. An `implicit_context.context_id` must resolve to a persisted entity whose type is `component`, `service`, or `shared_infrastructure`; unresolved and literal arguments carry no local record reference. Each `field_origins` entry is discriminated: `kind: derivation` resolves to a derivation, `kind: review` resolves to a review, and any other kind fails validation. Every decision status candidate's source/evidence references resolve locally, its status is canonical, and `status_evidence_ids` equals the sorted union of the retained candidates' evidence. Proposal and review target locators contain target kind, stable ID, and content digest. Before successor materialization, they must resolve exactly in the immutable input catalog; on publication they may instead resolve through the verified parent/base ancestry when that exact predecessor version was replaced. `create_record` alone has a null target ID/digest. Superseded reviews resolve in the frozen review ledger. A decision's non-null `predecessor_identity` is a complete external `{snapshot_id, record_id, content_digest, reason}` locator and must resolve to a decision in the named verified parent snapshot. Both `decision_analysis` and `decision_diagnostic` warnings require a locally resolving decision ID; the former uses the general decision-analysis shape while the latter requires the complete over-specification diagnostic fields. Source, analysis-source, and global variants omit the decision ID. Every edge endpoint must resolve to a persisted record whose kind is allowed by `EDGE_ENDPOINT_KINDS`; concern and consequence endpoints are ordinary entities or role-tagged claims, and review endpoints are records in `reviews.jsonl`. `edge_discriminator` is an empty object for every edge except `PROHIBITS`; that type requires exactly `{"prohibited_predicate": <controlled predicate>}` and includes it in identity. Reviews of ranking records and decision-diagnostic warnings remain ledger/report annotations and intentionally do not emit `REVIEW_OF` graph edges. There is no synthetic node namespace.

Typed proposal validation is exhaustive. `create_record` has null target/path and a complete typed record object; `replace_field` has an exact target, schema-declared non-array pointer, and replacement value; `add_alias` targets one entity, has null path, and a normalized alias string; `merge_entities` targets an entity and provides at least two exact entity locators plus one canonical locator; `split_entity` targets an entity and provides at least two nonempty typed partitions; `link_decision` targets a decision and provides nonempty exact claim locators; `rewrite_report_text` targets a decision/ranking/decision-diagnostic warning and provides bounded replacement prose. Unknown keys, kinds, target kinds, or malformed shapes fail typed validation. All shapes can be retained as diagnostic proposals, but V1 successor materialization accepts only `replace_field` whose target kind and exact pointer occur in `CORRECTABLE_FIELDS_V1`; an `accept_proposal` review for any other kind or path is invalid until that cascade is versioned and implemented.

Lineage adds nullable `predecessor_snapshot_id` and `successor_snapshot_id`. A null snapshot locator requires a local endpoint; a non-null locator must resolve the exact stable ID and content digest through `external_resolver`. Derivation `external_inputs` use the same resolver. This is the only permitted cross-snapshot reference form. Validation reports every dangling/wrong-kind reference before publication.

Use `importlib.resources.files("architecture_graph.resources")` to load one JSON object, reject any resource whose `schema_version` is not integer `1`, and hash its canonical bytes. `validate_typed_record` returns sorted `ValidationIssue(field, message)` values instead of raising so staging can report every missing field. Extend the Phase 1 derivation validator rather than replacing it: `producer_kind: deterministic` requires `created_at: null`, while `llm` and `human` require a non-null string accepted by the same `canonical_utc_event_time` helper used by `build_derivation_record`; offsets, fractional/noncanonical spellings, and invalid calendar values fail. When a derivation has `external_inputs`, validate each complete `{snapshot_id, kind, record_id, content_digest}` locator and its digest syntax; those locators intentionally resolve through an immutable parent snapshot rather than the current bundle's local-ID table.

Create `terms-en-v1.json`:

```json
{"acronym_pattern":"^(?:[A-Z][A-Z0-9]*)(?:[ -][A-Z0-9]+)*$","generic_hubs":["application","architecture","component","data","platform","service","system"],"glossary_headings":["definitions","glossary","terminology"],"identifier_pattern":"^(?:[A-Za-z][A-Za-z0-9]*)(?:[_.:/-][A-Za-z0-9]+)+$|^[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+$","schema_version":1,"stop_terms":["a","an","and","are","as","at","be","by","for","from","in","is","it","of","on","or","that","the","this","to","with"]}
```

Create `predicates-v1.json` with all approved predicates and surfaces:

```json
{"canonical_predicates":{"addresses":["address","addresses"],"calls":["call","calls","invoke","invokes"],"causes":["cause","causes","result in","results in"],"constrains":["constrain","constrains","limit","limits"],"depends_on":["depend on","depends on","rely on","relies on"],"deployed_on":["deploy on","deployed on","run on","runs on"],"justified_by":["because of","justify by","justified by"],"owned_by":["own by","owned by"],"prohibits":["forbid","forbids","prohibit","prohibits"],"publishes_to":["emit to","emits to","publish to","publishes to"],"reads_from":["read from","reads from"],"replaces":["replace","replaces"],"requires":["need","needs","require","requires","use","uses"],"subscribes_to":["consume from","consumes from","subscribe to","subscribes to"],"supersedes":["supersede","supersedes"],"trades_off_with":["trade off with","trades off with"],"writes_to":["persist to","persists to","write to","writes to"]},"schema_version":1}
```

Create `extraction-rules-en-v1.json`:

```json
{"applicabilities":["active","considered","contextual","rejected","unknown"],"claim_roles":["consequence","constraint","context","decision","observation","option","rationale"],"condition_markers":["if","unless","when"],"dependency_labels":{"coordination":["conj"],"object":["attr","dative","dobj","obj","oprd"],"passive_subject":["csubjpass","nsubjpass"],"subject":["csubj","nsubj"]},"effective_time_markers":{"valid_from":["effective from","from"],"valid_to":["until"]},"environment_scope_markers":{"development":["dev","development"],"production":["prod","production"],"staging":["stage","staging"],"test":["test","testing"]},"fallback_patterns":{"active":"^(?P<subject>[A-Za-z][A-Za-z0-9_.:/ -]*?)\\s+(?P<modal>must|should|may|will)?\\s*(?P<predicate>[A-Za-z]+(?:\\s+[A-Za-z]+){0,2})\\s+(?P<object>[A-Za-z0-9][A-Za-z0-9_.:/ -]*)$","imperative":"^(?P<predicate>[A-Z][A-Za-z]+(?:\\s+[A-Za-z]+){0,2})\\s+(?P<object>[A-Za-z0-9][A-Za-z0-9_.:/ -]*)$"},"modalities":["indicative","may","must","planned","should","unknown"],"modality_markers":{"may":["can","may"],"must":["must","shall"],"planned":["plan to","will"],"should":["ought to","should"]},"negation_markers":["never","no","not"],"polarities":["negative","positive"],"schema_version":1,"section_role_mappings":{"alternatives":"option","background":"context","consequences":"consequence","constraints":"constraint","context":"context","decision":"decision","drivers":"rationale","options":"option","rationale":"rationale","risks":"consequence"}}
```

Create `entity-rules-v1.json`:

```json
{"alias_similarity":{"metric":"character_ngram_jaccard","ngram_size":3,"require_same_declared_scope":true,"require_same_entity_type":true,"threshold":0.72},"diagram_declaration_types":{"component":"component","database":"data_store","interface":"interface","queue":"shared_infrastructure"},"entity_types":["component","concern","consequence","data_store","event","interface","service","shared_infrastructure","unknown"],"predicate_argument_types":{"addresses":{"object":"concern"},"calls":{"object":"interface"},"has_consequence":{"object":"consequence"},"publishes_to":{"object":"event"},"reads_from":{"object":"data_store"},"subscribes_to":{"object":"event"},"writes_to":{"object":"data_store"}},"schema_version":1,"suffix_types":{" api":"interface"," database":"data_store"," db":"data_store"," event":"event"," queue":"shared_infrastructure"," service":"service"," topic":"shared_infrastructure"}}
```

Type resolution order is explicit diagram declaration, predicate argument role, normalized suffix, then `unknown`. Declared entity scope is the relation's canonical scope object; an empty object means undeclared scope and is distinct from any explicit environment. Alias similarity lowercases/casefolds, pads neither side, builds unique character n-grams of the configured size, and computes set Jaccard; strings shorter than the n-gram size compare only by exact normalized equality. A threshold match emits `ALIAS_CANDIDATE` only when type and scope gates pass.

Create `decision-rules-v1.json`:

```json
{"adr_anchor_headings":["decision"],"decision_statuses":["absent","accepted","deprecated","proposed","rejected","superseded"],"explicit_decision_phrases":["the decision is","we choose","we decide"],"prescriptive_modalities":["must","should"],"prescriptive_predicates":["prohibits","requires"],"schema_version":1,"source_authority_precedence":["narrative_note","proposal_or_draft","maintained_architecture","approved_policy_or_constraint","accepted_adr_or_active_standard"],"status_mappings":{"accepted":["accepted","approved"],"deprecated":["deprecated"],"proposed":["draft","proposed"],"rejected":["declined","rejected"],"superseded":["replaced","superseded"]}}
```

Create `architect-questions-v1.json`:

```json
{"questions":{"consequence":"What consequence or trade-off justifies carrying this prescription?","driver":"What documented driver or risk requires this prescription?","scope":"Where does this prescription apply, and where does it explicitly not apply?","status":"What is the current decision status, and what evidence establishes it?"},"schema_version":1}
```

Load-time validation rejects unknown keys, missing keys, duplicate array members, a configured enum not present in `SCHEMA_ENUMS`, a predicate surface assigned to two canonical predicates, an unrecognized section-role target, or a decision-status surface assigned twice. Tests cover each failure rather than silently accepting a partially understood rule file.

Add package data to `pyproject.toml`:

```toml
[tool.setuptools.package-data]
architecture_graph = ["resources/*.json"]
```

- [ ] **Step 4: Add the real shared catalog helper**

Create `tests/helpers/phase2_catalog.py` with factory functions that pass records through `finalize_record`, construct `RecordCatalog`, `TermIndex`, `DiagnosticResult`, and `ProjectionSelection`, and use only stable fixed IDs. Later tasks extend this helper; no task imports a helper before the file exists.

- [ ] **Step 5: Run focused and cumulative tests**

```bash
uv run pytest tests/test_analysis_types.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: focused and cumulative tests pass; compileall exits 0.

- [ ] **Step 6: Commit the analysis contracts**

```bash
git add pyproject.toml scripts/architecture_graph/canonical.py scripts/architecture_graph/records.py scripts/architecture_graph/analysis_types.py scripts/architecture_graph/schemas.py scripts/architecture_graph/resources tests/helpers/phase2_catalog.py tests/test_analysis_types.py
git commit -m "feat: define deterministic analysis records"
```

### Task 2: Pinned No-Download NLP Runtime

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `scripts/architecture_graph/nlp.py`
- Create: `tests/helpers/__init__.py`
- Create: `tests/helpers/nlp_docs.py`
- Create: `tests/test_nlp.py`

**Interfaces:**
- Produces: `ModelArtifactLimits(max_paths=8192, max_files=4096, max_bytes=536870912)`, `RuntimeWarningTemplate`, `NlpRuntime`, `ParsedSegment`, and `ParsedCorpus`; `ParsedCorpus` carries finalized warnings, stable-sorted `derivations`, and an immutable `derivation_by_capability` map.
- Produces: `hash_installed_model_artifact(package_root: Path, limits: ModelArtifactLimits = ModelArtifactLimits()) -> str`; it is the sole bounded artifact routine used by both status and index runtime loading.
- Produces: `load_nlp_runtime(config: ProjectConfig) -> NlpRuntime`.
- Produces: `parse_corpus(corpus, runtime, configuration_digest, pipeline_digest) -> ParsedCorpus`.

- [ ] **Step 1: Write failing missing-model, provenance, and stable-order tests**

Create `tests/test_nlp.py`:

```python
import pytest
import spacy

from architecture_graph.analysis_types import IngestedCorpus
from architecture_graph.config import ProjectConfig
from architecture_graph.nlp import (
    ModelArtifactLimits,
    hash_installed_model_artifact,
    load_nlp_runtime,
    parse_corpus,
)
from architecture_graph.records import finalize_record
from tests.helpers.nlp_docs import runtime_with_capabilities


def test_missing_model_is_visible_and_never_downloaded(monkeypatch) -> None:
    monkeypatch.setattr(spacy, "load", lambda name: (_ for _ in ()).throw(OSError(name)))
    monkeypatch.setattr(
        spacy.cli,
        "download",
        lambda name: (_ for _ in ()).throw(AssertionError(f"download attempted: {name}")),
    )
    runtime = load_nlp_runtime(ProjectConfig(spacy_model="missing_en_model"))
    assert runtime.model_name == "spacy-blank-en"
    assert runtime.capabilities == ("tokenization",)
    assert runtime.warning_templates[0].code == "model_unavailable"
    assert runtime.model_artifact_digest is None


def test_parse_corpus_sorts_segments_and_labels_tokenizer_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        spacy,
        "load",
        lambda name: (_ for _ in ()).throw(OSError(name)),
    )
    source = finalize_record({"id": "source:one", "kind": "source"})
    segments = [
        finalize_record({"id": "segment:z", "kind": "segment", "source_version_id": "source:one", "text": "Second."}),
        finalize_record({"id": "segment:a", "kind": "segment", "source_version_id": "source:one", "text": "First."}),
    ]
    corpus = IngestedCorpus.from_records([source], segments, [], [])
    runtime = load_nlp_runtime(ProjectConfig(spacy_model="missing_en_model"))
    parsed = parse_corpus(corpus, runtime, "sha256:config", "sha256:pipeline")
    assert [item.segment_id for item in parsed.segments] == ["segment:a", "segment:z"]
    assert {item["method"] for item in parsed.derivations} == {"rule_tokenization"}
    tokenization = parsed.derivation_by_capability["tokenization"]
    assert tokenization["method"] == "rule_tokenization"
    assert tokenization["model"] == "spacy-blank-en"
    assert parsed.warnings[0]["warning_scope"] == "global"
    assert parsed.warnings[0]["source_version_id"] is None
    assert parsed.warnings[0]["derivation_ids"] == [tokenization["id"]]


def test_statistical_capability_gets_its_own_accurate_derivation() -> None:
    runtime = runtime_with_capabilities("tokenization", "named_entities")
    source = finalize_record({"id": "source:one", "kind": "source"})
    segment = finalize_record(
        {"id": "segment:one", "kind": "segment", "source_version_id": "source:one", "text": "Checkout"}
    )
    parsed = parse_corpus(
        IngestedCorpus.from_records([source], [segment], [], []),
        runtime,
        "sha256:config",
        "sha256:pipeline",
    )
    assert parsed.derivation_by_capability["tokenization"]["method"] == (
        "rule_tokenization"
    )
    assert parsed.derivation_by_capability["named_entities"]["method"] == (
        "statistical_nlp"
    )
    assert len(parsed.derivations) == 2


def test_model_artifact_hash_is_confined_regular_and_bounded(tmp_path) -> None:
    package = tmp_path / "fixture_model"
    package.mkdir()
    (package / "config.cfg").write_bytes(b"model")
    first = hash_installed_model_artifact(
        package, ModelArtifactLimits(max_files=1, max_bytes=5)
    )
    assert first.startswith("sha256:")

    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    (package / "escape.bin").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        hash_installed_model_artifact(package)

    (package / "escape.bin").unlink()
    (package / "second.bin").write_bytes(b"x")
    with pytest.raises(ValueError, match="path limit"):
        hash_installed_model_artifact(
            package,
            ModelArtifactLimits(max_paths=1, max_files=10, max_bytes=100),
        )
    with pytest.raises(ValueError, match="file limit"):
        hash_installed_model_artifact(
            package, ModelArtifactLimits(max_files=1, max_bytes=100)
        )
    with pytest.raises(ValueError, match="byte limit"):
        hash_installed_model_artifact(
            package, ModelArtifactLimits(max_files=10, max_bytes=5)
        )
```

Run:

```bash
uv run pytest tests/test_nlp.py -q
```

Expected: FAIL because `architecture_graph.nlp` and the Phase 2 dependencies do not exist.

- [ ] **Step 2: Add and lock the NLP dependencies**

Add to `[project].dependencies` in `pyproject.toml`:

```toml
"scikit-learn>=1.9,<2",
"spacy>=3.8,<4",
```

Run:

```bash
uv lock
uv sync
```

Expected: the lock records spaCy and scikit-learn; no language model is downloaded.

- [ ] **Step 3: Implement runtime identity and parsed-corpus ordering**

Create `scripts/architecture_graph/nlp.py` with frozen `ModelArtifactLimits`, `RuntimeWarningTemplate`, `NlpRuntime`, `ParsedSegment`, and `ParsedCorpus`. `NlpRuntime` has exactly `nlp: Language`, `model_name: str`, `spacy_version: str`, `model_version: str | None`, `model_artifact_digest: str | None`, `capabilities: tuple[str, ...]`, and `warning_templates: tuple[RuntimeWarningTemplate, ...]`. `ParsedCorpus` has exactly `segments: tuple[ParsedSegment, ...]`, `warnings: tuple[Record, ...]`, `derivations: tuple[Record, ...]`, and `derivation_by_capability: Mapping[str, Record]`; freeze the mapping with `MappingProxyType`. `load_nlp_runtime` calls `spacy.load` only for a configured installed package, catches `OSError`, creates `spacy.blank("en")` plus `sentencizer`, and returns an inert `RuntimeWarningTemplate(code, message)` rather than a record. A configured null model selects the blank tokenizer without a missing-model warning. The runtime has no configuration/pipeline digests yet and therefore must not finalize a warning or invent provenance. It never imports or calls a downloader.

`hash_installed_model_artifact` first resolves one existing package root, then performs an incremental directory walk without following symlinks. At each directory, consume `os.scandir` entries only until the remaining path budget plus one, reject `model artifact path limit exceeded` before materializing more, sort that bounded batch by NFC-normalized relative POSIX path, and continue. The total visited-entry cap is 8,192. Ignore only `__pycache__` directories and `.pyc`/`.pyo` files. Every other entry must remain beneath the resolved package root and be a regular file according to `lstat`; reject symlinks and special files visibly. Before reading a file, increment the file count and its `st_size`; fail with `model artifact file limit exceeded` above 4,096 files or `model artifact byte limit exceeded` above 536,870,912 bytes. Hash each admitted file by NFC-normalized POSIX relative path, a separator, its byte length, and SHA-256 content read in fixed one-MiB chunks. An over-limit or unsafe package fails runtime loading and freshness computation; it never falls back to an incomplete digest. `load_nlp_runtime`, deterministic index fingerprinting, and read-only `memory_status` call this one routine with the same default limits. Record the observed spaCy distribution version, model metadata version, and artifact digest. Capabilities are stable sorted values from `tokenization`, `dependency_parse`, `noun_chunks`, and `named_entities`; expose `noun_chunks` only together with `dependency_parse`.

`parse_corpus` pipes segment text in stable ID order and creates capability-accurate deterministic derivations. `tokenization` maps to `rule_tokenization`; `dependency_parse` maps to `dependency_parse`; `noun_chunks` reuses the dependency-parse derivation that made the chunks possible; and `named_entities` maps to a separate `statistical_nlp` derivation. Each derivation uses all parsed segment IDs, falling back to sorted source IDs when the corpus has sources but no segments, and uses a distinct output kind/identity key so its stable ID cannot collide. `ParsedCorpus.derivation_by_capability` maps each available capability to its exact persisted derivation and `ParsedCorpus.derivations` is the stable-ID-sorted deduplicated tuple of those values. For a fully empty corpus it returns no parsed segments, warning records, derivations, or capability map. Derivation model fields come from the observed runtime, and configuration/pipeline digests are the supplied actual values. Finalize each runtime warning template as a `warning_scope: global` warning with null source/span, possible role `parser_runtime`, and the tokenization derivation ID. `ParsedCorpus.warnings` and all `.derivations` are merged into the eventual snapshot exactly once.

Create `tests/helpers/nlp_docs.py`:

```python
import spacy
from spacy.language import Language
from spacy.tokens import Doc

from architecture_graph.nlp import NlpRuntime, ParsedSegment


def parsed_segment(
    nlp: Language,
    *,
    segment_id: str,
    source_version_id: str,
    words: list[str],
    heads: list[int],
    deps: list[str],
    pos: list[str],
    lemmas: list[str],
    sent_starts: list[bool],
) -> ParsedSegment:
    doc = Doc(
        nlp.vocab,
        words=words,
        heads=heads,
        deps=deps,
        pos=pos,
        lemmas=lemmas,
        sent_starts=sent_starts,
    )
    return ParsedSegment(segment_id, source_version_id, doc)


def runtime_with_capabilities(*capabilities: str) -> NlpRuntime:
    """Build the frozen no-download test runtime."""
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    return NlpRuntime(
        nlp=nlp,
        model_name="fixture-en",
        spacy_version=spacy.__version__,
        model_version="1.0.0",
        model_artifact_digest="sha256:" + "a" * 64,
        capabilities=tuple(sorted(capabilities)),
        warning_templates=(),
    )
```

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_nlp.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass without a model download.

- [ ] **Step 5: Commit the runtime**

```bash
git add pyproject.toml uv.lock scripts/architecture_graph/nlp.py tests/helpers/__init__.py tests/helpers/nlp_docs.py tests/test_nlp.py
git commit -m "feat: add deterministic NLP runtime"
```

### Task 3: Term Discovery and Sparse TF-IDF Dictionary

**Files:**
- Create: `scripts/architecture_graph/terms.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_terms.py`

**Interfaces:**
- Produces: `normalize_term(surface: str) -> str`.
- Produces: `discover_terms(corpus, parsed, configuration_digest, pipeline_digest) -> TermDiscoveryResult`.
- Produces: `build_term_index(terms: Sequence[Record]) -> TermIndex`.
- Produces: `TermIndex.from_snapshot(reader: SnapshotReader) -> TermIndex`, which streams `terms.jsonl` and delegates to `build_term_index` without loading any unrelated record family.

- [ ] **Step 1: Write failing salience, evidence, heading, and acronym tests**

Create `tests/test_terms.py` using three real segments: two repeat generic `system component` prose and one contains heading/acronym/identifier candidates `Checkout Service`, `OrderPlaced`, and `PCI DSS`.

```python
def test_distinct_architecture_terms_keep_evidence_and_outscore_boilerplate(
    term_corpus,
) -> None:
    result = discover_terms(
        term_corpus.corpus,
        term_corpus.parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    terms = {item["normalized"]: item for item in result.terms}
    assert terms["orderplaced"]["tfidf"]["max"] > terms["system"]["tfidf"]["max"]
    assert terms["orderplaced"]["evidence_ids"]
    assert terms["system"]["generic_hub"] is True
    assert terms["checkout service"]["term_kind"] == "heading_phrase"
    assert terms["pci dss"]["term_kind"] == "acronym"
    assert type(terms["orderplaced"]["vocabulary_index"]) is int
    assert terms["orderplaced"]["idf"] > 0
    assert {item["method"] for item in result.derivations} == {"rule", "tfidf"}
    local_derivations = {record["id"] for record in result.derivations}
    upstream_derivations = {record["id"] for record in term_corpus.parsed.derivations}
    assert all(
        set(item["derivation_ids"]) <= local_derivations | upstream_derivations
        for item in result.terms
    )
    if "named_entities" in term_corpus.parsed.derivation_by_capability:
        assert term_corpus.parsed.derivation_by_capability["named_entities"]["id"] in (
            terms["orderplaced"]["derivation_ids"]
        )


def test_one_normalized_surface_gets_one_precedence_selected_lexical_kind(
    term_corpus,
) -> None:
    result = discover_terms(
        term_corpus.corpus,
        term_corpus.parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    checkout = [item for item in result.terms if item["normalized"] == "checkout service"]
    assert len(checkout) == 1
    assert checkout[0]["term_kind"] == "heading_phrase"


def test_identical_source_copies_do_not_refit_lexical_statistics(
    term_corpus,
) -> None:
    baseline = discover_terms(
        term_corpus.corpus,
        term_corpus.parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    copied_corpus, copied_parsed = term_corpus.with_identical_source_copy()
    copied = discover_terms(
        copied_corpus,
        copied_parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    lexical = lambda result: {
        item["normalized"]: (item["idf"], item["tfidf"])
        for item in result.terms
    }
    assert lexical(copied) == lexical(baseline)
    assert next(
        item for item in copied.terms if item["normalized"] == "orderplaced"
    )["independent_source_count"] == 1
```

Run:

```bash
uv run pytest tests/test_terms.py -q
```

Expected: FAIL because term discovery does not exist.

- [ ] **Step 2: Implement candidates and TF-IDF without ranking nouns as decisions**

Normalize NFC, collapse whitespace, and casefold. Collect heading phrases, glossary forms, noun chunks and named entities when capabilities exist, acronyms, identifiers, and one-to-three-token normalized n-grams. Collapse candidate classifications to exactly one lexical record per normalized form with this precedence: glossary, acronym, identifier, heading phrase, named entity, noun phrase, n-gram. A lower-precedence observation still contributes its surfaces and evidence to the selected record. Every candidate retains surface forms, source versions, segment IDs, evidence IDs, and the exact upstream capability derivation IDs that produced it. Named-entity observations cite `parsed.derivation_by_capability["named_entities"]`; noun chunks cite `dependency_parse`; token-derived acronym/identifier/n-gram observations cite `tokenization`; structural heading/glossary observations need only the term-stage rule derivation. `TermDiscoveryResult.derivations` returns the new rule and TF-IDF derivations; upstream parsed derivations remain in `ParsedCorpus.derivations` and are referenced, not copied or relabeled.

Fit exactly one `TfidfVectorizer` over stable segment order after source-byte deduplication. Group sources by `source.content_hash`, choose the lexicographically lowest source ID as that byte group’s canonical representative, and fit only its segments. Do not deduplicate the persisted mentions or evidence: all source versions remain attached to the resulting term, while `independent_source_count` counts distinct content hashes.

```python
canonical_source_ids = {
    min(str(source["id"]) for source in group)
    for _, group in groupby_content_hash(corpus.sources)
}
fit_segments = tuple(
    segment for segment in corpus.segments
    if str(segment["source_version_id"]) in canonical_source_ids
)
```

Fit the vectorizer over `fit_segments`:

```python
vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 3),
    token_pattern=r"(?u)\b[A-Za-z][A-Za-z0-9_.:-]*\b",
    vocabulary={term: index for index, term in enumerate(sorted(candidate_terms))},
    norm="l2",
    use_idf=True,
    smooth_idf=True,
    sublinear_tf=False,
)
```

Each term identity hashes normalized form plus term kind. Store sorted surface forms; mention, segment, and independent-source counts; stable vocabulary index; exact fitted IDF; maximum and nonzero-mean TF-IDF; generic-hub flag; evidence IDs; term-normalizer resource digest; the returned `rule` and `tfidf` derivation IDs; and every capability derivation that actually contributed an observation. Never attach a statistical capability derivation to a term observed only by structural rules. `build_term_index` exposes immutable maps by ID, `(normalized, term_kind)`, lexical normalized form, controlled-predicate normalized form, casefolded surface, and vocabulary index, plus the IDF vector and normalizer digest reconstructed entirely from `terms.jsonl`. One normalized spelling may exist once in the lexical map and once in the controlled-predicate map; it never overwrites either. Reject duplicate kind keys, duplicate coordinates, coordinate gaps, or inconsistent IDF values.

- [ ] **Step 3: Run focused and cumulative tests**

```bash
uv run pytest tests/test_terms.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass.

- [ ] **Step 4: Commit term discovery**

```bash
git add scripts/architecture_graph/terms.py tests/helpers/phase2_catalog.py tests/test_terms.py
git commit -m "feat: discover architecture terms"
```

### Task 4: Deterministic Prose and Diagram Relation Candidates

**Files:**
- Create: `scripts/architecture_graph/relations.py`
- Modify: `tests/helpers/nlp_docs.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_relations.py`

**Interfaces:**
- Produces: `extract_relation_candidates(corpus, parsed, configuration_digest, pipeline_digest) -> RelationCandidateResult`.
- Recognizes active, passive, copular, imperative, coordinated, Mermaid, and PlantUML forms.
- Retains incomplete tuples in `candidates` with their warnings and exposes only complete tuples in `claim_eligible_candidates`, which is the collection passed to qualification and claim materialization.

- [ ] **Step 1: Write failing relation-shape and provenance tests**

Create `tests/test_relations.py`; its fixture includes one missing-object candidate and one missing-subject candidate, each with exact evidence:

```python
def test_active_passive_imperative_and_coordination_are_deterministic(
    relation_corpus,
) -> None:
    result = extract_relation_candidates(
        relation_corpus.corpus,
        relation_corpus.parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    tuples = {
        (
            item.subject_surface,
            item.predicate_surface,
            item.object_surface,
            item.subject_origin,
        )
        for item in result.candidates
    }
    assert ("Checkout", "publishes", "OrderPlaced", "explicit") in tuples
    assert ("Platform", "owns", "Ledger", "dependency_resolved") in tuples
    assert ("implicit system context", "Use", "PostgreSQL", "heading_context") in tuples
    assert ("Checkout", "publishes", "OrderCancelled", "explicit") in tuples


def test_diagram_edge_is_typed_and_incomplete_tuple_is_only_a_warning(
    relation_corpus,
) -> None:
    result = extract_relation_candidates(
        relation_corpus.corpus,
        relation_corpus.parsed,
        "sha256:config",
        "sha256:pipeline",
    )
    diagram = next(item for item in result.candidates if item.metadata["syntax"] == "mermaid")
    assert (diagram.subject_surface, diagram.object_surface) == ("Checkout", "Orders")
    assert any(item["code"] == "incomplete_relation" for item in result.warnings)
    assert any(item.object_surface is None for item in result.candidates)
    assert any(item.subject_surface is None for item in result.candidates)
    assert all(
        item.subject_surface is not None and item.object_surface is not None
        for item in result.claim_eligible_candidates
    )
    assert {
        item.id for item in result.claim_eligible_candidates
    } < {item.id for item in result.candidates}
    persisted_derivations = {
        item["id"]
        for item in (*result.derivations, *relation_corpus.parsed.derivations)
    }
    assert all(
        set(item.derivation_ids) <= persisted_derivations for item in result.candidates
    )
```

Run:

```bash
uv run pytest tests/test_relations.py -q
```

Expected: FAIL because relation extraction does not exist.

- [ ] **Step 2: Implement ordered dependency and typed-diagram rules**

Use these dependency sets:

```python
SUBJECT_DEPS = frozenset({"nsubj", "csubj"})
PASSIVE_SUBJECT_DEPS = frozenset({"nsubjpass", "csubjpass"})
OBJECT_DEPS = frozenset({"dobj", "obj", "attr", "oprd", "dative"})
COORD_DEPS = frozenset({"conj"})
```

Apply rules in this order: typed diagram statement; passive predicate with passive subject and agent/by object; active predicate with subject and direct object; copular root; imperative root with object and heading context; coordinated subject/object Cartesian expansion. When only tokenizer capability exists, apply a versioned anchored regex fallback for explicit `<identifier or noun phrase> <modal?> <controlled verb phrase> <object>` and imperative `<controlled verb> <object>` forms. Mark the extraction-stage fallback derivation method `rule`, never `dependency_parse`.

Persist every recognized candidate, including one with a missing subject or object, in `RelationCandidateResult.candidates`; attach `incomplete_relation` warnings to those incomplete records. Derive `claim_eligible_candidates` by retaining only complete subject-predicate-object tuples. Task 5 consumes that filtered tuple, while reports and diagnostics can still inspect the incomplete candidates and their evidence. Every prose candidate cites both its extraction-stage derivation and the exact upstream `tokenization` or `dependency_parse` derivation it consumed; typed diagram candidates do not invent an NLP dependency.

Phrase text comes from token subtrees in token order. Candidate identity hashes segment ID, normalized sentence span, subject, predicate, object, syntax, and rule version. Confidence is 0.95 for typed diagram edges, 0.90 for active/passive dependency forms, 0.85 for copular forms, 0.75 for imperative context, and 0.70 for tokenizer-only fallback. Store heading path, section role, ADR ID/status, syntax, evidence, and actual stage derivation IDs. Sort candidates by stable ID.

- [ ] **Step 3: Run focused and cumulative tests**

```bash
uv run pytest tests/test_relations.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass.

- [ ] **Step 4: Commit relation extraction**

```bash
git add scripts/architecture_graph/relations.py tests/helpers/nlp_docs.py tests/helpers/phase2_catalog.py tests/test_relations.py
git commit -m "feat: extract deterministic relation candidates"
```

### Task 5: Modality, Polarity, Condition, Scope, Time, and Role

**Files:**
- Create: `scripts/architecture_graph/qualifiers.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_qualifiers.py`

**Interfaces:**
- Produces: `qualify_relations(candidates, corpus, configuration_digest, pipeline_digest) -> QualificationResult`.
- Keeps decision status on the eventual decision rather than copying it into every contextual claim.

- [ ] **Step 1: Write failing qualifier independence tests**

Create `tests/test_qualifiers.py`:

```python
def test_must_not_has_one_canonical_representation(qualification_fixture) -> None:
    result = qualify_relations(
        qualification_fixture.candidates,
        qualification_fixture.corpus,
        "sha256:config",
        "sha256:pipeline",
    )
    prohibited = next(
        item for item in result.relations if item.candidate.object_surface == "credit card numbers"
    )
    assert prohibited.modality == "must"
    assert prohibited.polarity == "negative"
    assert prohibited.predicate_surface == "store"


def test_scope_condition_time_role_and_applicability_are_independent(
    qualification_fixture,
) -> None:
    result = qualify_relations(
        qualification_fixture.candidates,
        qualification_fixture.corpus,
        "sha256:config",
        "sha256:pipeline",
    )
    relation = next(
        item for item in result.relations if item.candidate.object_surface == "OrderPlaced"
    )
    assert relation.conditions == ("when payment succeeds",)
    assert relation.scope == {"environments": ("production",)}
    assert relation.effective_time == {
        "valid_from": "2026-08-01",
        "valid_to": None,
        "basis": "explicit",
    }
    assert relation.claim_role == "constraint"
    assert relation.applicability == "active"


def test_rejected_option_never_becomes_active(qualification_fixture) -> None:
    result = qualify_relations(
        qualification_fixture.candidates,
        qualification_fixture.corpus,
        "sha256:config",
        "sha256:pipeline",
    )
    option = next(
        item for item in result.relations if item.candidate.metadata["section_role"] == "option"
    )
    assert option.claim_role == "option"
    assert option.applicability == "rejected"
```

Run:

```bash
uv run pytest tests/test_qualifiers.py -q
```

Expected: FAIL because qualification does not exist.

- [ ] **Step 2: Implement ordered, versioned qualifier transforms**

Use the resource-defined modality tokens with canonical values `must`, `should`, `may`, `planned`, `indicative`, and `unknown`. Strip modal and negation tokens from the stored predicate surface. Encode `must not` as modality `must` plus polarity `negative`.

Extract conditions only from anchored `when`, `if`, and `unless` clauses; environment scope only from explicit production/staging/development/test markers; effective dates only from ISO dates attached to `from` or `until`; and section role from structural segment metadata. Missing values remain empty/unknown. Emit `unresolved_scope_marker` or `unresolved_status_marker` only when a marker exists but cannot be parsed.

Map section roles to claim roles: decision→decision, constraint→constraint, option→option, rationale/driver→rationale, consequence/risk→consequence, context→context, observation→observation. Rationale, consequence, and context are contextual. Options are considered unless the option itself or its decision anchor is rejected. Accepted/deprecated selected decision or constraint relations are active; rejected ones are rejected; absent status is unknown until the decision reducer attaches status.

Return one persisted rule derivation and add its ID to every qualified relation. Sort warnings and relations by stable ID.

- [ ] **Step 3: Run focused and cumulative tests**

```bash
uv run pytest tests/test_qualifiers.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass.

- [ ] **Step 4: Commit qualification**

```bash
git add scripts/architecture_graph/qualifiers.py tests/helpers/phase2_catalog.py tests/test_qualifiers.py
git commit -m "feat: qualify architecture relations"
```

### Task 6: Controlled Predicates, Conservative Entities, and Claim Ledger

**Files:**
- Create: `scripts/architecture_graph/ontology.py`
- Create: `scripts/architecture_graph/entities.py`
- Create: `scripts/architecture_graph/claims.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_claims.py`

**Interfaces:**
- Produces: `load_predicate_ontology(path=None) -> PredicateOntology` and `normalize_predicate(surface, ontology) -> Mapping[str, str] | None`.
- Produces: `classify_entity(argument, relation, rules) -> tuple[str, Mapping[str, tuple[str, ...]]]` and `alias_similarity(left, right, rules) -> float`.
- Produces: `resolve_entities(relations, corpus: IngestedCorpus, terms, declared_aliases, configuration_digest, pipeline_digest) -> EntityResolutionResult`; corpus is the explicit immutable source/segment/evidence context for source-local resolution and provenance.
- Produces: `materialize_claims(relations, resolution, corpus, ontology, configuration_digest, pipeline_digest) -> ClaimMaterializationResult`.
- Produces: `argument_identity_payload`, `claim_identity_payload`, `claim_stable_id`, and `validate_claim`.

- [ ] **Step 1: Write failing predicate, identity, resolution, and invariant tests**

Create `tests/test_claims.py` with these assertions:

```python
from architecture_graph.analysis_types import TermIndex


def test_predicate_normalization_retains_surface() -> None:
    ontology = load_predicate_ontology()
    assert normalize_predicate("publishes to", ontology) == {
        "canonical": "publishes_to",
        "surface": "publishes to",
    }


def test_alias_and_unambiguous_acronym_resolve_but_similarity_does_not_merge(
    claim_fixture,
) -> None:
    result = resolve_entities(
        claim_fixture.relations,
        claim_fixture.corpus,
        claim_fixture.terms,
        {"checkout-api": "Checkout Service"},
        "sha256:config",
        "sha256:pipeline",
    )
    subject = result.arguments_by_candidate_id["candidate:checkout"][0]
    assert subject.kind == "entity_ref"
    assert subject.entity_id == claim_fixture.checkout_entity_id
    assert any(item["edge_type"] == "ALIAS_CANDIDATE" for item in result.edges)
    assert len([item for item in result.entities if item["canonical_key"] in {"order", "orders"}]) == 2
    assert alias_similarity("Order", "Orders", load_entity_rules()) == 0.75
    assert all(
        item["declared_scope"] == {"environments": ["production"]}
        for item in result.entities
        if item["canonical_key"] == "orders"
    )


def test_declared_alias_with_multiple_scoped_targets_stays_unresolved(
    claim_fixture,
) -> None:
    result = resolve_entities(
        claim_fixture.relations_with_ambiguous_checkout_targets(),
        claim_fixture.corpus,
        claim_fixture.terms,
        {"checkout-api": "checkout-service"},
        "sha256:config",
        "sha256:pipeline",
    )
    subject = result.arguments_by_candidate_id["candidate:checkout"][0]
    assert subject.kind == "unresolved_span"
    assert any(item["code"] == "ambiguous_alias_target" for item in result.warnings)


def test_claim_identity_excludes_confidence_but_includes_scope(claim_fixture) -> None:
    first = claim_fixture.materialized_claim
    confidence_change = {**first, "extraction_confidence": 0.51}
    wording_change = {
        **first,
        "subject": {
            **first["subject"],
            "surface": "the checkout service",
            "origin": "dependency_resolved",
        },
    }
    scope_change = claim_fixture.with_scope(first, "staging")
    assert claim_identity_payload(first) == claim_identity_payload(confidence_change)
    assert claim_identity_payload(first) == claim_identity_payload(wording_change)
    assert claim_identity_payload(first) != claim_identity_payload(scope_change)


def test_imperative_context_resolves_only_to_one_nearest_explicit_system(
    claim_fixture,
) -> None:
    resolved = resolve_entities(
        claim_fixture.imperative_relations_under_unique_component,
        claim_fixture.corpus,
        claim_fixture.terms,
        {},
        "sha256:config",
        "sha256:pipeline",
    )
    subject = resolved.arguments_by_candidate_id["candidate:imperative"][0]
    assert subject.kind == "implicit_context"
    assert subject.context_id == claim_fixture.checkout_entity_id
    assert claim_fixture.validate_resolution_snapshot(resolved) == ()

    ambiguous = resolve_entities(
        claim_fixture.imperative_relations_under_tied_components,
        claim_fixture.corpus,
        claim_fixture.terms,
        {},
        "sha256:config",
        "sha256:pipeline",
    )
    subject = ambiguous.arguments_by_candidate_id["candidate:imperative"][0]
    assert subject.kind == "unresolved_span"
    assert any(
        item["code"] == "unresolved_implicit_context"
        for item in ambiguous.warnings
    )


def test_same_tuple_claims_under_one_heading_use_local_occurrence_anchor(
    claim_fixture,
) -> None:
    first, second = claim_fixture.opposite_same_tuple_claims()
    assert first["claim_anchor"]["canonical_tuple_ordinal"] == 0
    assert second["claim_anchor"]["canonical_tuple_ordinal"] == 1
    assert claim_stable_id(first) != claim_stable_id(second)


def test_materialized_claim_has_complete_evidence_and_provenance(claim_fixture) -> None:
    result = materialize_claims(
        claim_fixture.relations,
        claim_fixture.resolution,
        claim_fixture.corpus,
        load_predicate_ontology(),
        "sha256:config",
        "sha256:pipeline",
    )
    claim = result.claims[0]
    assert validate_claim(claim) == ()
    assert claim["assertion_kind"] == "extracted"
    assert claim["evidence_ids"]
    persisted = {item["id"] for item in result.derivations}
    assert set(claim["derivation_ids"]) <= persisted | claim_fixture.upstream_derivation_ids
    assert claim["field_origins"]["/qualifiers/modality"][0]["kind"] == "derivation"


def test_uncontrolled_predicate_is_retained_as_warning_not_silently_dropped(
    claim_fixture,
) -> None:
    result = materialize_claims(
        claim_fixture.relations_with_uncontrolled_predicate("orchestrates"),
        claim_fixture.resolution,
        claim_fixture.corpus,
        load_predicate_ontology(),
        "sha256:config",
        "sha256:pipeline",
    )
    assert not any(
        item["predicate"]["surface"] == "orchestrates" for item in result.claims
    )
    warning = next(item for item in result.warnings if item["code"] == "unresolved_predicate")
    assert warning["warning_scope"] == "analysis_source"
    assert warning["evidence_ids"] == ["evidence:orchestrates"]
    assert warning["input_ids"] == ["segment:orchestrates"]
    assert warning["candidate_key"] == "candidate:orchestrates"


def test_lexical_and_controlled_predicate_same_spelling_round_trip(
    claim_fixture,
) -> None:
    reader = claim_fixture.snapshot_with_term_kinds(
        normalized="requires",
        lexical_kind="ngram",
        controlled_kind="controlled_predicate",
    )
    index = TermIndex.from_snapshot(reader)
    lexical = index.lexical_by_normalized["requires"]
    controlled = index.controlled_predicate_by_normalized["requires"]
    assert lexical["id"] != controlled["id"]
    assert index.by_normalized_kind[("requires", "ngram")] == lexical
    assert index.by_normalized_kind[("requires", "controlled_predicate")] == controlled


def test_byte_identical_explicit_document_copies_share_claim_occurrences(
    claim_fixture,
) -> None:
    baseline = materialize_claims(*claim_fixture.materialization_inputs())
    copied = materialize_claims(
        *claim_fixture.with_identical_explicit_document_copy().materialization_inputs()
    )
    assert {claim["id"] for claim in copied.claims} == {
        claim["id"] for claim in baseline.claims
    }
    baseline_claim = baseline.claim_by_predicate("publishes_to")
    copied_claim = copied.claim_by_predicate("publishes_to")
    assert claim_identity_payload(copied_claim) == claim_identity_payload(baseline_claim)
    assert claim_fixture.semantic_claim_payload(copied_claim) == (
        claim_fixture.semantic_claim_payload(baseline_claim)
    )
    assert len(copied_claim["source_version_ids"]) == 2
    assert set(copied_claim["evidence_ids"]) > set(baseline_claim["evidence_ids"])
    assert copied.controlled_predicate("publishes_to")["independent_source_count"] == 1
```

Run:

```bash
uv run pytest tests/test_claims.py -q
```

Expected: FAIL because predicate normalization, entity resolution, and claims do not exist.

- [ ] **Step 2: Implement collision-free predicate lookup and conservative arguments**

Invert the predicate resource and reject a surface assigned to two canonical predicates. At function entry build immutable maps from the supplied `IngestedCorpus`: source by source-version ID, segment by segment ID, evidence by evidence ID, and source-local segments ordered by exact source span then stable ID. Reject a relation whose segment/source/evidence IDs do not resolve through those maps. Resolve argument forms in two passes. First materialize explicit/literal arguments and entities. Then resolve an imperative subject by: the nearest explicit allowed entity in the same heading segment; the nearest ancestor heading whose normalized text resolves uniquely in compatible scope; then the unique allowed component/service/shared-infrastructure entity in that Phase 1 `logical_source_id` and compatible scope. Compute distance only from the resolved segment heading ancestry and evidence/source spans in the corpus, never from ad hoc candidate metadata. Stable ID provides deterministic ordering but never breaks a semantic tie. Zero or tied nearest candidates retain an `unresolved_span` and emit evidence-backed `unresolved_implicit_context`; a unique result becomes `implicit_context` with that persisted entity ID. Continue with configured alias; exact normalized identifier; unique acronym; distinct new entity. `declared_aliases` comes only from the validated, digest-covered Phase 1 `ProjectConfig.aliases` map. An alias target must resolve to exactly one existing canonical identifier under the relation's scope; zero or multiple matches retain an `unresolved_span` and emit `unresolved_alias_target` or `ambiguous_alias_target` rather than choosing. Apply the exact entity type, declared-scope, character-trigram Jaccard, 0.72 threshold, and same-type/same-scope gates from `entity-rules-v1.json`. A qualifying similarity emits an `ALIAS_CANDIDATE` edge with evidence and a persisted graph-rule derivation but never changes identity; a type or scope mismatch emits no alias edge.

Entity identity hashes entity type, normalized canonical key, and canonical declared scope. Store sorted surface forms, evidence, derivations, and field origins. An unresolved phrase becomes a valid `unresolved_span` argument and remains visible in the canonical claim ledger; only a missing object prevents claim materialization and emits a warning. Task 12 excludes unresolved arguments from semantic centrality without erasing them from evidence review.

- [ ] **Step 3: Materialize only invariant-satisfying claims**

Claim argument and claim identity use:

```python
def argument_identity_payload(argument: Mapping[str, object]) -> Mapping[str, object]:
    kind = argument["kind"]
    if kind == "entity_ref":
        return {"kind": kind, "entity_id": argument["entity_id"]}
    if kind == "literal":
        return {
            "kind": kind,
            "value": argument["value"],
            "datatype": argument["datatype"],
            "unit": argument.get("unit"),
        }
    if kind == "unresolved_span":
        return {
            "kind": kind,
            "normalized": normalize_term(str(argument["unresolved_text"])),
        }
    if kind == "implicit_context":
        return {"kind": kind, "context_id": argument["context_id"]}
    raise ValueError(f"unsupported argument kind: {kind}")


def claim_identity_payload(claim: Mapping[str, object]) -> Mapping[str, object]:
    qualifiers = claim["qualifiers"]
    return {
        "subject": argument_identity_payload(claim["subject"]),
        "predicate": {"canonical": claim["predicate"]["canonical"]},
        "object": argument_identity_payload(claim["object"]),
        "scope": qualifiers["scope"],
        "source_lineage": claim["source_lineage"],
        "claim_anchor": claim["claim_anchor"],
    }
```

Every extracted claim contains subject, canonical predicate plus surface, object, modality, polarity, sorted conditions and scopes, effective-time basis, claim role, applicability, initially empty decision IDs, assertion kind `extracted`, extraction confidence, evidence, derivations, logical source lineage, source-version IDs, segment ID, heading/source metadata, claim anchor, and field origins. Source lineage uses `logical_source_id`, not source-version ID.

Before assigning claim ordinals, coalesce byte-copy occurrences. Map each candidate to its Phase 1 source content hash and form a path-independent occurrence key from `logical_source_id`, normalized heading path, canonical subject-predicate-object-scope key, source content hash, and exact source-relative evidence span. Candidates with the same key represent one semantic occurrence even when they came from several paths with the same explicit document ID. Require their normalized semantic/qualifier payloads to agree, choose the lexicographically smallest segment ID only for the claim's scalar representative segment field, and canonical-union every evidence ID, source-version ID, contributing derivation ID, surface, and field origin. A disagreement under one occurrence key is a deterministic validation error rather than a new ordinal. Then, for each normalized heading and canonical tuple group, sort only these coalesced occurrences by source-relative span and the canonical occurrence key—never by candidate, segment, source-version, or path ID—and assign `canonical_tuple_ordinal` from zero. Adding a byte-identical path can therefore enrich provenance but cannot insert an ordinal or change claim identity.

The claim anchor is `{logical_source_id, normalized_heading_path, canonical_tuple_ordinal}`; it excludes surface text, parser origin, modality, polarity, conditions, and effective time. Build no claim without subject, object, controlled predicate, evidence, and derivation. A complete candidate whose predicate surface has no controlled mapping remains visible through its segment/evidence and produces an `unresolved_predicate` warning. The warning stores the ephemeral candidate stable key in non-reference `candidate_key`, while `input_ids` contains only durable segment/derivation records and `evidence_ids` contains durable evidence; it never creates a dangling candidate reference, disappears silently, or produces a claim.

For every canonical predicate used by a materialized claim, also return one evidence-backed `term_kind: controlled_predicate` record in `ClaimMaterializationResult.ontology_terms`. It has `vocabulary_index: null`, `idf: 0.0`, the same `normalizer_resource_digest` used by every lexical term, a separate `ontology_resource_digest`, sorted surfaces/evidence from its claims, mention/segment/independent-source counts from those claims, zero-valued `tfidf` statistics, `generic_hub: false`, and the claim-stage derivation. Typed term validation requires `ontology_resource_digest` for `controlled_predicate`, forbids it on lexical terms, and permits a null vocabulary index only for `controlled_predicate` with zero IDF and zero TF-IDF values. `TermIndex.from_snapshot` validates the common normalizer digest across both term kinds, then ignores null coordinates when reconstructing the contiguous lexical IDF vector. Analysis merges ontology terms into `terms.jsonl` by stable ID before graph construction. Task 12 therefore represents `CLAIM_PREDICATE` as claim→controlled-predicate-term without a synthetic unpersisted node.

Claim-stage derivation is returned and persisted. Upstream relation/qualification derivations remain referenced where they contributed. Validate discriminated arguments, allowed enums, extracted/inferred evidence rules, sorted sets, finite confidence, and field-origin shape.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_claims.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass.

- [ ] **Step 5: Commit canonical claims**

```bash
git add scripts/architecture_graph/ontology.py scripts/architecture_graph/entities.py scripts/architecture_graph/claims.py tests/helpers/phase2_catalog.py tests/test_claims.py
git commit -m "feat: materialize canonical architecture claims"
```

### Task 7: Source-Anchored Decisions and Semantic Decision Digest

**Files:**
- Create: `scripts/architecture_graph/decisions.py`
- Modify: `scripts/architecture_graph/schemas.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_decisions.py`

**Interfaces:**
- Produces: `reduce_decisions(corpus, claims, configuration_digest, pipeline_digest) -> DecisionReductionResult`.
- Produces: `canonical_claim_key(claim) -> Mapping[str, object]` and `decision_semantic_digest(decision, claims_by_id) -> str`.
- Uses the sole `decision_identity_payload(decision)` contract declared in Task 1 for stable IDs and later identity-change classification.
- Uses no similarity-based merge.

- [ ] **Step 1: Write failing anchor, status-evidence, merge, and digest tests**

Create `tests/test_decisions.py` to prove: one ADR can contain two local decision anchors; an ADR without a Decision heading receives one document-root anchor; first prescriptive claim is primary; driver, option, rationale, and consequence attach by structural role; accepted status cites its front-matter evidence; rejected options remain non-active; exact explicit IDs merge; similar prose without an exact key remains separate; evidence/confidence-only changes do not change semantic digest; modality, scope, role, consequence, or status changes do.

```python
def test_adr_status_and_roles_reduce_without_activating_options(decision_fixture) -> None:
    result = reduce_decisions(
        decision_fixture.corpus,
        decision_fixture.claims,
        "sha256:config",
        "sha256:pipeline",
    )
    decision = next(
        item for item in result.decisions if "ADR-001" in item["explicit_decision_ids"]
    )
    assert decision["decision_status"] == "accepted"
    assert decision["status_evidence_ids"] == ["evidence:adr-001-status"]
    assert decision["primary_claim_ids"] == ["claim:publish"]
    assert set(decision["member_claim_ids"]) == {
        "claim:consequence",
        "claim:driver",
        "claim:option",
        "claim:publish",
    }
    assert result.updated_claims_by_id["claim:option"]["applicability"] != "active"


def test_two_local_decision_headings_under_one_adr_remain_distinct(
    decision_fixture,
) -> None:
    result = reduce_decisions(
        decision_fixture.corpus_with_two_adr_decision_headings,
        decision_fixture.claims_under_two_adr_decision_headings,
        "sha256:config",
        "sha256:pipeline",
    )
    assert len(result.decisions) == 2
    assert len({item["source_anchor"]["normalized_heading_anchor"] for item in result.decisions}) == 2


def test_path_only_rename_does_not_change_decision_identity(decision_fixture) -> None:
    before = reduce_decisions(
        decision_fixture.rename_before_corpus,
        decision_fixture.rename_before_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    after = reduce_decisions(
        decision_fixture.rename_after_corpus,
        decision_fixture.rename_after_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    assert before.decisions[0]["source_anchor"]["relative_path"] != after.decisions[0][
        "source_anchor"
    ]["relative_path"]
    assert before.decisions[0]["id"] == after.decisions[0]["id"]


def test_explicit_identity_is_independent_of_source_path_and_logical_source(
    decision_fixture,
) -> None:
    left, right = decision_fixture.same_explicit_decision_from_two_sources
    assert decision_identity_payload(left) == decision_identity_payload(right)


def test_conflicting_highest_authority_statuses_are_ambiguous(
    decision_fixture,
) -> None:
    result = reduce_decisions(
        decision_fixture.conflicting_status_corpus,
        decision_fixture.exact_cross_source_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    decision = result.decisions[0]
    assert decision["decision_status"] == "absent"
    assert decision["status_resolution"] == "ambiguous"
    assert {item["status"] for item in decision["status_candidates"]} == {
        "accepted",
        "proposed",
    }
    warning = next(
        item for item in result.warnings
        if item["code"] == "ambiguous_decision_status"
    )
    assert warning["warning_scope"] == "decision_analysis"
    assert warning["decision_id"] == decision["id"]


def test_similar_non_adr_decisions_remain_separate(decision_fixture) -> None:
    result = reduce_decisions(
        decision_fixture.corpus,
        decision_fixture.similar_non_adr_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    assert len(result.decisions) == 2


def test_exact_non_adr_merge_has_stable_survivor_and_rejects_many_to_many(
    decision_fixture,
) -> None:
    merged = reduce_decisions(
        decision_fixture.unique_exact_key_corpus,
        decision_fixture.unique_exact_key_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    candidate_ids = decision_fixture.unique_exact_key_candidate_ids
    assert [item["id"] for item in merged.decisions] == [min(candidate_ids)]
    assert merged.decisions[0]["source_anchor_aliases"] == sorted(
        set(candidate_ids) - {min(candidate_ids)}
    )

    ambiguous = reduce_decisions(
        decision_fixture.many_to_many_exact_key_corpus,
        decision_fixture.many_to_many_exact_key_claims,
        "sha256:config",
        "sha256:pipeline",
    )
    assert len(ambiguous.decisions) == 4
    merge_warnings = [
        item for item in ambiguous.warnings
        if item["code"] == "ambiguous_decision_merge"
    ]
    assert {item["decision_id"] for item in merge_warnings} == {
        item["id"] for item in ambiguous.decisions
    }
    assert all(item["warning_scope"] == "decision_analysis" for item in merge_warnings)


def test_semantic_digest_ignores_added_corroboration(decision_fixture) -> None:
    first = decision_semantic_digest(decision_fixture.decision, decision_fixture.claims_by_id)
    changed = decision_fixture.with_added_evidence_and_confidence()
    assert first == decision_semantic_digest(decision_fixture.decision, changed)
```

Run:

```bash
uv run pytest tests/test_decisions.py -q
```

Expected: FAIL because the decision reducer does not exist.

- [ ] **Step 2: Implement the approved reducer order and exact merge boundary**

Apply rules in order: ADR ID plus local Decision heading; ADR ID plus document root when no Decision heading exists; non-ADR heading only when it owns a prescriptive claim; first prescriptive claim as primary; context/driver/rationale, option, and consequence attachment; source status and supersession; cross-source merge only by a unique exact explicit-ID/local-anchor key or exact primary canonical claim key plus normalized scope; deterministic support/conflict/alias edges without merging. Two distinct local Decision headings in one ADR are two anchors even though they share the ADR ID. An explicit-ID merge requires the normalized local heading anchor to match (or the same document-root marker) and must be unique on each logical source; ID alone never collapses multiple local anchors. An exact primary-key/scope cluster also requires at most one candidate anchor from each logical source. A repeated key on either source makes the whole cluster ambiguous: keep every candidate and emit `ambiguous_decision_merge`. For a valid non-ADR cluster, keep the lexicographically smallest full candidate decision ID and record every other full identity in sorted `source_anchor_aliases`.

Every decision persists:

```text
source_anchor: anchor_kind, logical_source_id, relative_path,
  normalized_heading_anchor, explicit_decision_id
source_anchor_aliases
explicit_decision_ids
logical_source_ids
primary_canonical_claim_key
canonical_claim_keys
primary_claim_ids
member_claim_ids
decision_status
status_resolution
status_candidates
status_evidence_ids
source_version_ids
derivation_ids
predecessor_identity
semantic_digest
```

Heading components use NFC, whitespace collapse, and casefold. Retain every evidence-backed source status candidate with source version, content hash, declared authority class, effective content-group authority class, and evidence IDs. Before status reduction, group all sources by `content_hash` and assign every occurrence in a group the least authoritative class present under `decision-rules-v1.json.source_authority_precedence`. Resolve only among candidates at the maximum effective group class: one distinct value becomes `decision_status`; conflicting values set `decision_status: absent`, `status_resolution: ambiguous`, and emit an evidence-backed `ambiguous_decision_status` warning. A high-authority path containing bytes already present at lower authority therefore cannot raise status precedence. No candidate uses `status_resolution: absent`; a unique winner uses `resolved`. `decision_status` is always one of proposed, accepted, rejected, deprecated, superseded, or `absent`; it is never null. The review-priority status-ambiguity feature reads `status_resolution` and the warning. Canonical claim keys contain canonical subject argument kind/key, predicate, object argument kind/key, and normalized scope. They exclude source lineage, modality, confidence, evidence, and derivation. Arrays are canonical-byte sorted and deduplicated.

Decision identity is computed only through `decision_identity_payload`: explicit ID plus local anchor when present; otherwise logical source, normalized heading anchor, and primary canonical claim key. `relative_path` remains content/provenance and a verified path-only rename keeps the ID. Cross-source explicit candidates with the same normalized explicit ID/local anchor share one identity; their logical sources preserve corroboration and no redundant alias ID is invented. Exact non-ADR cross-source merges retain the lexicographically smallest full candidate identity and record all other distinct candidate IDs as aliases; uniqueness gates are checked before choosing the survivor.

Emit `ambiguous_decision_status` and `ambiguous_decision_merge` as `warning_scope: decision_analysis`. The status warning names its one decision. A many-to-many merge ambiguity emits one warning per retained decision, naming that decision and the durable claim/evidence inputs that made the candidate cluster ambiguous. Warning IDs are stable over code, decision ID, and canonical inputs; ephemeral in-memory candidate objects never appear in `input_ids`.

- [ ] **Step 3: Implement membership edges and semantic digest**

Emit `BELONGS_TO_DECISION`, `JUSTIFIED_BY`, `HAS_CONSEQUENCE`, explicit `SUPERSEDES`, and exact-rule `SUPPORTS` edges with evidence and the returned reducer derivation. Return updated claim successors whose decision IDs, role, or applicability changed; preserve their deterministic field origins.

The semantic digest hashes decision status, `status_resolution`, the sorted distinct candidate status values (but not their source/evidence IDs or duplicate corroboration), supersession targets, and sorted unique role-tagged semantic payloads: canonical argument types/keys/scopes, predicate, modality, polarity, normalized conditions/scope, effective time, claim role, and applicability. An absent→ambiguous or ambiguous→resolved transition therefore advances semantic history. Exclude record/content IDs, duplicate corroboration, wording, paths, evidence, confidence, derivations, origins, reviews, graph metrics, ranks, and report text.

- [ ] **Step 4: Run the first deterministic-ledger checkpoint**

```bash
uv run pytest tests/test_analysis_types.py tests/test_nlp.py tests/test_terms.py tests/test_relations.py tests/test_qualifiers.py tests/test_claims.py tests/test_decisions.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all focused and cumulative tests pass; every term, entity, claim, decision, edge, and warning resolves its persisted deterministic derivation.

- [ ] **Step 5: Commit decisions**

```bash
git add scripts/architecture_graph/decisions.py scripts/architecture_graph/schemas.py tests/helpers/phase2_catalog.py tests/test_decisions.py
git commit -m "feat: reduce claims into architecture decisions"
```

### Task 8: Conflict and Three-Valued Over-Specification Diagnostics

**Files:**
- Create: `scripts/architecture_graph/diagnostics.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_diagnostics.py`

**Interfaces:**
- Produces: `analyze_diagnostics(claims, decisions, edges, warnings, configuration_digest, pipeline_digest) -> DiagnosticResult`.
- Lower helpers `detect_conflicts(..., derivation_id)` and `evaluate_overspecification(..., derivation_id)` never invent unreturned derivation IDs.
- `DiagnosticResult` contains conflict edges, over-specification warnings, and all diagnostic derivations.

- [ ] **Step 1: Write failing conflict and three-valued review tests**

Create `tests/test_diagnostics.py`:

```python
def test_conflict_requires_shared_key_and_overlapping_scope_and_time(
    diagnostic_fixture,
) -> None:
    result = analyze_diagnostics(
        diagnostic_fixture.claims,
        diagnostic_fixture.decisions,
        diagnostic_fixture.edges,
        (),
        "sha256:config",
        "sha256:pipeline",
    )
    pairs = {(item["from_id"], item["to_id"]) for item in result.conflict_edges}
    assert ("claim:postgres", "claim:mysql") in pairs
    assert ("claim:production", "claim:development") not in pairs
    assert ("claim:old", "claim:new") not in pairs


def test_missing_driver_and_consequence_is_flagged(diagnostic_fixture) -> None:
    record = diagnostic_fixture.evaluate("decision:unsupported-database")
    assert record["result"] == "flagged"
    assert record["severity"] == "high"
    assert record["dimensions"]["driver"] == "missing"
    assert record["dimensions"]["consequence"] == "missing"


def test_overlapping_coverage_warning_makes_a_dimension_unknown(
    diagnostic_fixture,
) -> None:
    record = diagnostic_fixture.evaluate("decision:warning-covered")
    assert record["result"] == "unknown"
    assert record["dimensions"]["consequence"] == "unknown"


def test_vendor_specificity_alone_never_flags(diagnostic_fixture) -> None:
    record = diagnostic_fixture.evaluate("decision:supported-postgresql")
    assert record["result"] == "not_flagged"
    assert record["severity"] == "none"
```

Run:

```bash
uv run pytest tests/test_diagnostics.py -q
```

Expected: FAIL because diagnostic analysis does not exist.

- [ ] **Step 2: Implement exact conflict matching with a persisted derivation**

A conflict requires the same canonical subject and predicate, overlapping normalized scope, overlapping effective-time interval, active/unknown applicability, and incompatible polarity, object, or active status. Emit one stable `CONTRADICTS` edge per canonical ordered claim pair. Store overlapping scope/time basis, claim IDs, evidence IDs, input IDs, and the graph-rule derivation returned in `DiagnosticResult.derivations`.

- [ ] **Step 3: Implement the defensive three-valued evaluator**

Evaluate only decisions containing modality must/should or predicate requires/prohibits. For the same decision and compatible scope/applicability/status, set:

- driver satisfied by an evidence-backed `ADDRESSES` or `JUSTIFIED_BY` path;
- consequence satisfied by `HAS_CONSEQUENCE` or `TRADES_OFF_WITH`;
- scope satisfied by explicit compatible scope or one known subject scope;
- status satisfied by accepted, non-conflicting status.

Absence is `unknown` only when a persisted overlapping warning identifies the corresponding role (`parse_failed`, `unsupported_construct`, `unresolved_scope_marker`, or `unresolved_status_marker`). Otherwise it is `missing`. Combine with:

```python
def overall_dimension_result(values: Mapping[str, str]) -> str:
    if "missing" in values.values():
        return "flagged"
    if "unknown" in values.values():
        return "unknown"
    return "not_flagged"
```

The durable warning uses the Phase 1 common envelope with `warning_scope: decision_diagnostic`, `code: possible_overspecification`, a human-readable message, null source version/span, possible role `decision`, and diagnostic derivation IDs. Its typed variant also has `diagnostic_type: possible_overspecification`, decision ID, result, severity, four dimensions, one versioned architect question, evidence/input IDs, and the same diagnostic derivation IDs. Global model warnings use `warning_scope: global`; source parser warnings omit `warning_scope` and retain a non-null source. Both driver and consequence missing is high; one missing or scope/status ambiguity is medium; not flagged is none. Vendor/version specificity, churn, and weak support may order records within a band but cannot change the result.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_diagnostics.py -q
uv run pytest -q
```

Expected: focused and cumulative tests pass.

- [ ] **Step 5: Commit diagnostics**

```bash
git add scripts/architecture_graph/diagnostics.py tests/helpers/phase2_catalog.py tests/test_diagnostics.py
git commit -m "feat: identify architecture review risks"
```

### Task 9: Immutable Proposal, Human Review, Successor, and Projection Rules

**Files:**
- Modify: `scripts/architecture_graph/claims.py`
- Create: `scripts/architecture_graph/reviews.py`
- Create: `scripts/architecture_graph/projections.py`
- Create: `tests/fixtures/reviews/raw-proposals.jsonl`
- Create: `tests/fixtures/reviews/raw-reviews.jsonl`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_review_projection.py`

**Interfaces:**
- Produces: `AuthorityPolicy.from_authorities(authorities) -> AuthorityPolicy`.
- Produces: `reduce_reviews(catalog, proposals, reviews, policy) -> ReviewProjection`.
- Produces: `effective_decision_review_status(decision_status, primary_claim_statuses) -> str`.
- Produces: `materialize_reviewed_successors(catalog, proposals, reviews, projection, configuration_digest, pipeline_digest) -> SuccessorMaterialization`.
- Produces: `materialize_reviewed_catalog(corpus, base_catalog, successors, parent_snapshot_id, configuration_digest, pipeline_digest) -> ReviewedMaterializationResult`.
- Produces: `reconcile_controlled_predicate_terms(claims, existing_terms, configuration_digest, pipeline_digest) -> tuple[tuple[Record, ...], tuple[Record, ...]]`, returning the complete lexical-plus-controlled term set and its new derivations.
- Produces: `select_projection(catalog, review_projection, lifecycle_lens, provenance_layer, successors=()) -> ProjectionSelection`.

- [ ] **Step 1: Add raw proposal/review events and failing projection tests**

`raw-proposals.jsonl` contains: same-identity modality replacement at `/qualifiers/modality`; identity-changing subject replacement at `/subject/entity_id`; and unreviewed alias proposal. Each proposal points to a finalized `producer_kind: llm` derivation built with fixed `created_at: 2026-07-19T10:00:00Z`; a fixture variant with null or offset-form time must fail typed validation. `raw-reviews.jsonl` contains: stale verification; lower-authority verify plus higher-authority dispute; equal-authority incompatible verdicts; accepted modality proposal; accepted subject proposal; rejected alias proposal; and explicit same-reviewer supersession. Every human review uses a fixed canonical `YYYY-MM-DDTHH:MM:SSZ` time. Test helpers parse every raw line and call `finalize_record`; hand-calculated digests do not enter fixtures.

Create `tests/test_review_projection.py`:

```python
from architecture_graph.schemas import CORRECTABLE_FIELDS_V1, validate_typed_record


def test_stale_reviews_do_not_apply_and_highest_authority_wins(review_fixture) -> None:
    projection = reduce_reviews(
        review_fixture.catalog,
        review_fixture.proposals,
        review_fixture.reviews,
        review_fixture.policy,
    )
    assert "review:stale" in projection.stale_review_ids
    assert projection.status_by_target[("claim", "claim:authority")] == "disputed"


def test_equal_authority_incompatible_verdicts_are_disputed(review_fixture) -> None:
    assert review_fixture.projection.status_by_target[("claim", "claim:equal")] == "disputed"


def test_field_review_semantics_are_conservative(review_fixture) -> None:
    field_verified = review_fixture.with_field_review(
        verdict="verify", field_path="/qualifiers/modality"
    )
    assert field_verified.status_by_target[("claim", "claim:modality")] == "unreviewed"
    field_disputed = review_fixture.with_field_review(
        verdict="dispute", field_path="/qualifiers/modality"
    )
    assert field_disputed.status_by_target[("claim", "claim:modality")] == "disputed"


@pytest.mark.parametrize(
    "review_id",
    [
        "review:field-reject",
        "review:correct-without-field",
        "review:correct-without-replacement",
        "review:accept-non-proposal",
    ],
)
def test_invalid_verdict_target_and_field_shapes_do_not_apply(
    review_fixture, review_id: str
) -> None:
    projection = review_fixture.projection_with_invalid_shape(review_id)
    assert review_id in projection.invalid_review_ids


@pytest.mark.parametrize(
    "proposal_kind",
    [
        "create_record",
        "replace_field",
        "add_alias",
        "merge_entities",
        "split_entity",
        "link_decision",
        "rewrite_report_text",
    ],
)
def test_every_proposal_kind_has_one_validated_shape(
    review_fixture, proposal_kind: str
) -> None:
    proposal = review_fixture.valid_proposal(proposal_kind)
    assert validate_typed_record(proposal, "proposal") == ()
    malformed = review_fixture.break_required_shape(proposal)
    assert validate_typed_record(malformed, "proposal")


@pytest.mark.parametrize(
    "unsupported_kind",
    [
        "create_record",
        "add_alias",
        "merge_entities",
        "split_entity",
        "link_decision",
        "rewrite_report_text",
    ],
)
def test_v1_cannot_accept_an_unimplemented_proposal_cascade(
    review_fixture, unsupported_kind: str
) -> None:
    projection = review_fixture.accept_proposal_of_kind(unsupported_kind)
    assert projection.accepted_proposal_ids == ()
    assert review_fixture.accept_review_id in projection.invalid_review_ids


def test_v1_materializes_only_allowlisted_claim_or_entity_fields(
    review_fixture,
) -> None:
    assert set(CORRECTABLE_FIELDS_V1) == {"claim", "entity"}
    corrected = review_fixture.direct_correction(
        target_kind="claim",
        field_path="/qualifiers/modality",
        replacement_value="must",
    )
    successor = corrected.catalog.get("claim", "claim:modality")
    assert successor["qualifiers"]["modality"] == "must"
    assert successor["field_origins"]["/qualifiers/modality"][-1]["kind"] == "review"


def test_predicate_correction_materializes_a_previously_unused_term_and_edge(
    review_fixture,
) -> None:
    corrected = review_fixture.direct_correction(
        target_kind="claim",
        field_path="/predicate/canonical",
        replacement_value="subscribes_to",
    )
    assert "subscribes_to" not in review_fixture.parent_controlled_predicates
    term = corrected.catalog.controlled_predicate("subscribes_to")
    claim = corrected.catalog.only_corrected_claim
    edge = corrected.catalog.edge("CLAIM_PREDICATE", claim["id"], term["id"])
    assert term["evidence_ids"] == claim["evidence_ids"]
    assert edge["target_id"] == term["id"]
    assert corrected.catalog.references_resolve()


@pytest.mark.parametrize(
    ("target_kind", "field_path"),
    [
        ("claim", "/id"),
        ("claim", "/evidence_ids"),
        ("decision", "/decision_status"),
        ("ranking", "/scores"),
    ],
)
def test_v1_rejects_successors_outside_the_correctable_table(
    review_fixture, target_kind: str, field_path: str
) -> None:
    before = review_fixture.ledger_bytes
    result = review_fixture.try_direct_correction(target_kind, field_path)
    assert result.invalid_review_ids == (review_fixture.correct_review_id,)
    assert result.successors == ()
    assert review_fixture.ledger_bytes == before


def test_entity_identity_correction_rekeys_and_cascades(review_fixture) -> None:
    result = review_fixture.direct_correction(
        target_kind="entity",
        field_path="/canonical_key",
        replacement_value="orders-v2",
    )
    successor = next(
        item for item in result.successors
        if item.get("predecessor_content_digest") == review_fixture.entity_digest
    )
    assert successor["id"] != review_fixture.entity_id
    assert any(
        item["predecessor_id"] == review_fixture.entity_id
        and item["successor_id"] == successor["id"]
        for item in result.lineage
    )
    assert review_fixture.entity_id not in result.cascaded_reference_ids


@pytest.mark.parametrize(
    ("direct", "primary", "expected"),
    [
        ("rejected", ("verified",), "rejected"),
        ("disputed", ("verified",), "disputed"),
        ("unreviewed", ("rejected", "rejected"), "rejected"),
        ("unreviewed", ("unreviewed", "rejected"), "disputed"),
        ("unreviewed", ("verified", "disputed"), "disputed"),
        ("verified", ("unreviewed",), "verified"),
        ("unreviewed", ("verified", "verified"), "verified"),
        ("unreviewed", ("unreviewed",), "unreviewed"),
    ],
)
def test_effective_decision_review_status_is_conservative(
    direct: str, primary: tuple[str, ...], expected: str
) -> None:
    assert effective_decision_review_status(direct, primary) == expected


def test_content_change_keeps_id_and_records_deterministic_llm_human_origins(
    review_fixture,
) -> None:
    result = review_fixture.materialize()
    successor = next(item for item in result.records if item["id"] == "claim:modality")
    assert successor["predecessor_content_digest"] == review_fixture.modality_digest
    assert successor["qualifiers"]["modality"] == "must"
    assert successor["field_origins"]["/qualifiers/modality"] == [
        {"kind": "derivation", "id": "derivation:deterministic"},
        {"kind": "derivation", "id": "derivation:llm"},
        {"kind": "review", "id": "review:accept-modality"},
    ]


def test_identity_change_creates_new_id_and_lineage(review_fixture) -> None:
    result = review_fixture.materialize()
    successor = next(
        item for item in result.records
        if item.get("predecessor_content_digest") == review_fixture.subject_digest
    )
    assert successor["id"] != "claim:subject"
    assert result.lineage[0]["predecessor_id"] == "claim:subject"
    assert result.lineage[0]["successor_id"] == successor["id"]


def test_reviewed_successors_cascade_and_rerun_semantics(review_fixture) -> None:
    reviewed = review_fixture.materialize_catalog()
    subject_successor = reviewed.catalog.get(
        "claim", review_fixture.subject_successor_id
    )
    assert subject_successor is not None
    assert review_fixture.subject_predecessor_id not in {
        claim_id
        for decision in reviewed.decisions
        for claim_id in decision["member_claim_ids"]
    }
    assert review_fixture.subject_successor_id in {
        claim_id
        for decision in reviewed.decisions
        for claim_id in decision["member_claim_ids"]
    }
    changed = reviewed.catalog.get("decision", "decision:modality")
    assert changed["semantic_digest"] != review_fixture.base_decision_digest
    assert reviewed.diagnostics.overspecification != review_fixture.base_diagnostics


def test_reviewed_decisions_record_exact_parent_ancestry(review_fixture) -> None:
    reviewed = review_fixture.materialize_catalog()
    same_id = reviewed.catalog.get("decision", "decision:modality")
    assert same_id["predecessor_identity"] == {
        "snapshot_id": review_fixture.parent_snapshot_id,
        "record_id": "decision:modality",
        "content_digest": review_fixture.base_decision_digest,
        "reason": "reviewed_successor",
    }
    changed = review_fixture.materialize_non_adr_primary_identity_change()
    successor = next(
        item for item in changed.decisions
        if item["id"] != review_fixture.non_adr_predecessor_id
    )
    lineage = next(
        item for item in changed.lineage
        if item["successor_id"] == successor["id"]
        and item["predecessor_id"] == review_fixture.non_adr_predecessor_id
    )
    assert lineage["predecessor_snapshot_id"] == review_fixture.parent_snapshot_id
    assert lineage["predecessor_id"] == review_fixture.non_adr_predecessor_id
    assert lineage["successor_snapshot_id"] is None


def test_unaccepted_proposal_is_diagnostic_only(review_fixture) -> None:
    current = select_projection(
        review_fixture.catalog,
        review_fixture.projection,
        LifecycleLens.CURRENT,
        ProvenanceLayer.ENRICHED,
    )
    review = select_projection(
        review_fixture.catalog,
        review_fixture.projection,
        LifecycleLens.REVIEW,
        ProvenanceLayer.ENRICHED,
    )
    assert current.diagnostic_proposals == ()
    assert [item["id"] for item in review.diagnostic_proposals] == [
        "proposal:unreviewed-alias"
    ]
```

Run:

```bash
uv run pytest tests/test_review_projection.py -q
```

Expected: FAIL because review reduction and projections do not exist.

- [ ] **Step 2: Implement policy validation and conservative review reduction**

`AuthorityPolicy` canonicalizes reviewer authorities and hashes them. A review applies only when reviewer ID, copied authority, authority-policy digest, target, target content digest, supersession ancestry, verdict, target kind, and field path validate. Retain stale/invalid IDs for reporting but exclude them from effective reduction. A later event from the same reviewer supersedes an earlier one only through explicit `supersedes_review_id`. Reduce at highest authority; incompatible equal-authority verdicts become disputed.

Whole-record verify→verified, reject→rejected, dispute→disputed. A field-level verify records assurance only for that field and leaves the whole target unreviewed. A field-level dispute conservatively makes the whole target disputed. `reject` requires a whole-record target with no field path. `correct` requires a target kind and exact pointer in `CORRECTABLE_FIELDS_V1` plus a replacement value. `accept_proposal` requires a proposal target; it authorizes materialization only when that proposal is `replace_field` and its underlying target kind/pointer is in the same table. Any invalid verdict/target/path/replacement shape is retained in `invalid_review_ids`, reported, and excluded from reduction. `accept_proposal` and `correct` authorize successor materialization but do not automatically mark the successor verified; every corrected successor begins unreviewed at the whole-record level and has a new content digest.

After target review reduction, compute each decision's effective review status in this exact order: direct rejected; direct disputed; every primary claim rejected; any primary claim disputed or a rejected primary mixed with a non-rejected primary; direct verified or all primary claims verified; otherwise unreviewed. An empty primary-claim set never satisfies the `all` rules. Reviews of rationale, option, context, and consequence claims remain report diagnostics and do not enter this decision aggregation. Store the result in `ReviewProjection.effective_status_by_target`; do not mutate the decision record.

- [ ] **Step 3: Implement field origins, identity changes, and lineage**

Support only exact `CORRECTABLE_FIELDS_V1` pointers; reject array-index and prefix-derived pointers. Apply a replacement to a copy, validate its complete typed shape, enums, discriminated arguments, local/external references, and field-origin map before it can enter the result. A content-only accepted `replace_field` proposal keeps the stable ID, sets predecessor content digest, recomputes content digest, and appends its real proposal derivation plus accepting review to the changed field origin. A direct `correct` event performs the same successor/digest work but appends only its human review origin plus the deterministic materialization derivation; it has no proposal. Copied fields retain their existing origins. An invalid successor produces no partial cascade.

Claim identity changes at subject, canonical predicate, object, normalized scope, or source lineage recompute claim ID and emit lineage. After all claim substitutions, call `reconcile_controlled_predicate_terms` over the complete reviewed claim set: retain lexical TF-IDF terms unchanged, rebuild the controlled-predicate subset from exactly the canonical predicates still used, materialize a stable term for a newly used predicate, and remove a controlled-predicate term only when no reviewed claim uses it. Recompute its sorted surfaces, evidence, segment/source counts, and derivations from the current claims while preserving the Task 6 controlled-term schema and normalizer/ontology digests. Every claim's canonical predicate must then resolve to exactly one controlled-predicate term before graph construction. An accepted direct or `replace_field` correction to any allowlisted entity identity pointer (`entity_type`, `canonical_key`, or `declared_scope`) likewise recomputes the entity ID, emits lineage, substitutes the new ID through every affected claim and edge, and then reruns decisions and diagnostics. Although merge/split proposal records remain valid diagnostics, V1 cannot accept them. Every successor/lineage/controlled-term reconciliation record cites the persisted deterministic review-materialization derivation and the accepting/correcting review where applicable. An accepted proposal additionally cites its real proposal derivation; a direct `correct` event has no proposal and never invents one.

Identity/content classification uses the same schema selectors used to create IDs: `argument_identity_payload` for claim arguments and `decision_identity_payload` for decisions. No code compares a whole source anchor, raw argument object, or path provenance to decide whether an identity changed.

- [ ] **Step 4: Implement lifecycle and provenance selection**

Before projection selection, implement `materialize_reviewed_catalog` as a full immutable cascade and pass the exact selected parent snapshot ID into it. Substitute accepted entity successors into every affected claim argument; recompute claim IDs/anchors and emit lineage. Replace accepted same-ID claim content, carry untouched claims once, reconcile the complete controlled-predicate term subset, and rewrite claim-bearing edges. Rerun `reduce_decisions` over the reviewed claim set so member IDs, applicability, semantic digests, and decision successors are current; then rerun diagnostics over the reviewed decisions/claims/edges. When a reviewed decision keeps its ID but changes content, set its external `predecessor_identity` to the exact parent snapshot decision ID/content digest with reason `reviewed_successor`. When a non-ADR primary-claim identity change produces a new decision ID, emit decision lineage from the exact parent decision version to the local successor (and set the successor predecessor locator). Build a fresh reviewed catalog and reject any dangling predecessor ID, unresolved claim-predicate term, or same-ID/different-content collision. The deterministic base catalog remains byte-for-byte unchanged. All cascade outputs cite persisted review-materialization or rerun derivations and retain deterministic, LLM, and human field origins.

Deterministic layer contains deterministic records. Enriched makes unaccepted proposal nodes available, but only the review lifecycle lens exposes them as diagnostic proposals. Reviewed substitutes accepted successors and frozen review status. Every `ProjectionSelection` copies the projection's sorted stale-review IDs, invalid-review IDs, and disputed targets alongside effective target status so reports and bounded queries can label diagnostic review state without re-reducing raw events. Current contains accepted decisions, active selected claims, and maintained observations and never exposes unaccepted proposals. Review adds absent/proposed/deprecated/disputed/conflicting/incomplete/stale records and proposal diagnostics. Historical retains all records captured by the selected immutable snapshot. V1 deliberately has no effective-time `as_of` selector; claims keep their intervals as data, and arbitrary time-point projection is deferred. Rejected/disputed records remain diagnostic and never emit semantic assertions.

- [ ] **Step 5: Run the review checkpoint**

```bash
uv run pytest tests/test_review_projection.py -q
uv run pytest tests/test_analysis_types.py tests/test_claims.py tests/test_decisions.py tests/test_diagnostics.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all focused and cumulative tests pass; unaccepted proposals cannot enter current decisions or claims.

- [ ] **Step 6: Commit review projection**

```bash
git add scripts/architecture_graph/claims.py scripts/architecture_graph/reviews.py scripts/architecture_graph/projections.py tests/fixtures/reviews tests/helpers/phase2_catalog.py tests/test_review_projection.py
git commit -m "feat: project immutable architecture reviews"
```

### Task 10: Intrinsic Features, Retrieval Documents, and Provisional Scores

**Files:**
- Create: `scripts/architecture_graph/resources/scoring-v1.json`
- Create: `scripts/architecture_graph/resources/impact-rules-v1.json`
- Create: `scripts/architecture_graph/features.py`
- Create: `scripts/architecture_graph/ranking.py`
- Modify: `scripts/architecture_graph/schemas.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_features.py`

**Interfaces:**
- Produces: `ScoringConfig.load_v1() -> ScoringConfig`.
- Produces: `compute_intrinsic_features(selection, terms, diagnostics, config) -> Mapping[str, IntrinsicDecisionFeatures]`.
- Produces: `build_decision_retrieval(decision, catalog, terms, max_evidence=3, excerpt_chars=400) -> Record`.
- Produces: `build_intrinsic_rankings(...) -> RankingResult`; the result includes rankings and their persisted scoring derivation.

- [ ] **Step 1: Add exact scoring configuration**

Create canonical `scoring-v1.json`:

```json
{"bridge":{"exact_node_limit":5000,"sample_size":256},"confidence_weights":{"extraction_confidence":0.4,"independent_corroboration":0.2,"provenance_completeness":0.25,"review_assurance":0.15},"context":{"evidence_fraction":0.3,"metadata_fraction":0.1,"omission_fraction":0.05,"summary_fraction":0.55},"context_traversal_weights":{"CONTRADICTS":1.0,"PROPOSES":0.25,"REVIEW_OF":0.25,"SUPPORTS":0.7,"SUPERSEDES":1.0},"criticality_weights":{"authority_and_commitment":0.25,"cross_cutting_scope":0.15,"impact_and_irreversibility":0.2,"independent_evidence_breadth":0.1,"lexical_salience":0.05,"persistence_across_snapshots":0.1,"structural_leverage":0.15},"edge_base_weights":{"ADDRESSES":0.9,"AFFECTS":0.5,"CALLS":0.8,"CAUSES":0.9,"CONSTRAINS":1.0,"DEPENDS_ON":0.9,"DEPLOYED_ON":0.5,"GOVERNS":1.0,"HAS_CONSEQUENCE":0.8,"JUSTIFIED_BY":0.9,"OWNED_BY":0.5,"PROHIBITS":1.0,"PUBLISHES_TO":0.8,"READS_FROM":0.8,"REPLACES":0.9,"REQUIRES":1.0,"SUBSCRIBES_TO":0.8,"SUPERSEDES":1.0,"TRADES_OFF_WITH":0.9,"WRITES_TO":0.8},"history":{"churn_transitions":3,"initial_persistence":0.5,"persistence_cap":1.0,"persistence_step":0.1},"impact_weights":{"data_ownership_or_persistence":0.15,"migration_or_lock_in":0.1,"public_interface_or_boundary":0.15,"quality_attribute":0.15,"shared_dependency":0.1,"system_structure":0.2,"trust_or_security_boundary":0.15},"modality_weights":{"indicative":0.5,"may":0.35,"must":1.0,"planned":0.4,"should":0.75,"unknown":0.25},"observation_status_factor":0.65,"pagerank":{"alpha":0.85,"max_iter":100,"tolerance":1e-10},"review_priority_weights":{"churn":0.2,"conflict":0.25,"derivation_risk":0.1,"missing_rationale":0.2,"scope_ambiguity":0.1,"stale_or_ambiguous_status":0.15},"rounding_places":8,"schema_version":1,"scope_weights":{"components":0.5,"concerns":0.2,"environments":0.15,"stakeholders":0.15},"source_authority_weights":{"accepted_adr_or_active_standard":1.0,"approved_policy_or_constraint":0.9,"maintained_architecture":0.75,"narrative_note":0.35,"proposal_or_draft":0.45},"status_factors":{"absent":0.65,"accepted":1.0,"deprecated":0.1,"proposed":0.35,"rejected":0.0,"superseded":0.0},"structural_weights":{"bridge":0.25,"degree":0.15,"pagerank":0.6}}
```

`ScoringConfig.load_v1()` also loads `decision-rules-v1.json.source_authority_precedence` as the single authority ordering. It rejects a missing/extra source-authority score or any score table that is not strictly monotonic in that ordering. Decision reduction uses the ordering only; scoring uses the validated numeric values. No second hard-coded authority order exists.

Create canonical `impact-rules-v1.json`:

```json
{"categories":{"data_ownership_or_persistence":{"entity_types":["data_store"],"predicates":["owned_by","reads_from","writes_to"],"term_markers":["data ownership","database","persistence","retention","storage"]},"migration_or_lock_in":{"entity_types":[],"predicates":["replaces","supersedes"],"term_markers":["lock-in","migration","vendor","version"]},"public_interface_or_boundary":{"entity_types":["event","interface"],"predicates":["calls","publishes_to","subscribes_to"],"term_markers":["api","contract","event","interface","schema"]},"quality_attribute":{"entity_types":["concern"],"predicates":["constrains","prohibits"],"term_markers":["availability","latency","performance","reliability","scalability"]},"shared_dependency":{"entity_types":["shared_infrastructure"],"predicates":["depends_on","requires"],"term_markers":["platform","shared infrastructure"]},"system_structure":{"entity_types":["component","service"],"predicates":["deployed_on","governs"],"term_markers":["boundary","component","deployment","topology"]},"trust_or_security_boundary":{"entity_types":["concern"],"predicates":["prohibits","requires"],"term_markers":["authentication","authorization","encryption","pci dss","pii","security","trust boundary"]}},"personalization":{"entity_types":["concern","data_store","interface","shared_infrastructure"],"term_markers":["constraint","data boundary","interface","shared infrastructure"]},"schema_version":1}
```

An impact flag is one only when a selected claim/edge with evidence matches at least one exact canonical predicate, entity type, or normalized term marker in that category. The match contributes its claim/edge/evidence IDs to the feature explanation. No substring or embedding inference is permitted. Personalization seeds use the same exact entity-type/term-marker table and only accepted-decision concerns or constraints.

- [ ] **Step 2: Write failing formula, order, input, and retrieval tests**

Create `tests/test_features.py`:

```python
from dataclasses import replace


def complete_features(decision_id: str) -> IntrinsicDecisionFeatures:
    return IntrinsicDecisionFeatures(
        decision_id=decision_id,
        decision_status_factor=1.0,
        authority_and_commitment=1.0,
        impact_and_irreversibility=1.0,
        cross_cutting_scope=1.0,
        independent_evidence_breadth=1.0,
        lexical_salience=1.0,
        conflict=1.0,
        missing_rationale=1.0,
        stale_or_ambiguous_status=0.0,
        scope_ambiguity=0.5,
        derivation_risk=0.15,
        extraction_confidence=0.8,
        provenance_completeness=1.0,
        independent_corroboration=2.0 / 3.0,
        review_assurance=0.25,
        input_ids=("claim:one", "decision:one"),
        derivation_ids=("derivation:one",),
    )


def test_provisional_scores_keep_three_dimensions_independent() -> None:
    scores = score_intrinsic_features(complete_features("decision:one"), ScoringConfig.load_v1())
    assert scores.criticality == 0.8
    assert scores.review_priority == 0.515
    assert scores.confidence == 0.74083333


def test_equal_scores_use_stable_decision_id() -> None:
    values = {key: complete_features(key) for key in ("decision:z", "decision:a")}
    result = build_intrinsic_rankings(
        values,
        {key: phase2_empty_retrieval() for key in values},
        LifecycleLens.REVIEW,
        ProvenanceLayer.DETERMINISTIC,
        ScoringConfig.load_v1(),
        "sha256:config",
        "sha256:pipeline",
    )
    assert [item["decision_id"] for item in result.rankings] == ["decision:a", "decision:z"]


def test_status_factor_multiplies_the_entire_criticality_sum() -> None:
    config = ScoringConfig.load_v1()
    accepted = score_intrinsic_features(
        complete_features("decision:accepted"), config
    )
    proposed_features = replace(
        complete_features("decision:proposed"),
        decision_status_factor=0.35,
    )
    rejected_features = replace(
        complete_features("decision:rejected"),
        decision_status_factor=0.0,
    )
    assert score_intrinsic_features(proposed_features, config).criticality == 0.28
    assert score_intrinsic_features(rejected_features, config).criticality == 0.0
    assert accepted.criticality == 0.8


def test_retrieval_uses_only_three_bounded_primary_excerpts(feature_fixture) -> None:
    retrieval = build_decision_retrieval(
        feature_fixture.decision,
        feature_fixture.catalog,
        feature_fixture.terms,
        max_evidence=3,
        excerpt_chars=400,
    )
    assert len(retrieval["evidence_ids"]) == 3
    assert all(len(text) <= 400 for text in retrieval["evidence_excerpts"])
    assert "background boilerplate" not in retrieval["search_document"]


def test_each_impact_flag_has_an_exact_evidence_backed_rule(feature_fixture) -> None:
    features = compute_intrinsic_features(
        feature_fixture.selection_with_all_impact_rules,
        feature_fixture.terms,
        (),
        ScoringConfig.load_v1(),
    )["decision:impact"]
    assert features.impact_flags == {
        "data_ownership_or_persistence": 1.0,
        "migration_or_lock_in": 1.0,
        "public_interface_or_boundary": 1.0,
        "quality_attribute": 1.0,
        "shared_dependency": 1.0,
        "system_structure": 1.0,
        "trust_or_security_boundary": 1.0,
    }
    assert all(features.impact_input_ids[key] for key in features.impact_flags)
```

Run:

```bash
uv run pytest tests/test_features.py -q
```

Expected: FAIL because features and rankings do not exist.

- [ ] **Step 3: Implement approved intrinsic feature rules**

Use frozen `IntrinsicDecisionFeatures` and `ScoreTriple`. First group supporting sources by `content_hash`; assign each group the minimum configured authority weight among its occurrences, then take the maximum across distinct groups. Compute exactly: authority/commitment from 0.60 of that group-aware authority plus 0.40 primary modality; seven evidence-backed impact category flags; unique scope counts with denominators 5/3/3/3; breadth `min(1, log(1+n)/log(6))`; primary-claim lexical salience 0.40 subject + 0.20 predicate + 0.40 object; diagnostic conflict; missing rationale; status ambiguity; scope ambiguity; derivation risk; evidence-weighted extraction confidence; six-field provenance completeness; independent corroboration; review assurance. All other evidence/source aggregates likewise deduplicate by content hash before a maximum, mean, count, or status factor can affect a score.

Compute `criticality = decision_status_factor * weighted_criticality_sum` using all seven configured criticality terms. The multiplier applies after the weighted sum: accepted 1.00, status-absent maintained material 0.65, proposed 0.35, deprecated 0.10, and rejected/superseded 0.00. Provisional criticality uses structural leverage 0.0 and persistence 0.50. Provisional review priority uses churn 0.0. Confidence is final. Missing evidence contributes zero except explicit absent-state weights.

Retrieval stores normalized search document, sorted identifiers and aliases, the term-normalizer resource digest, and an L2-normalized sparse vector as sorted `{vocabulary_index, weight}` pairs using the `terms.jsonl` vocabulary and IDF values. It also stores bounded evidence terms, no more than three evidence IDs, and excerpts clipped at a sentence/source-line boundary to 400 characters. Full background prose never enters the search document. A retrieval vector with an unknown coordinate, duplicate coordinate, mismatched normalizer digest, or non-unit nonzero norm fails validation.

Ranking identity hashes decision, lifecycle lens, provenance layer, scoring resource digest, and version. Store `ranking_phase: intrinsic`, null semantic-projection digest, separate scores/ranks, named features, retrieval, input IDs, derivation IDs, and content digest. Rank each score independently by descending rounded value and stable decision ID.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_features.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: focused and cumulative tests pass; every ranking cites the scoring derivation returned in `RankingResult`.

- [ ] **Step 5: Commit intrinsic ranking**

```bash
git add scripts/architecture_graph/resources/scoring-v1.json scripts/architecture_graph/resources/impact-rules-v1.json scripts/architecture_graph/features.py scripts/architecture_graph/ranking.py scripts/architecture_graph/schemas.py tests/helpers/phase2_catalog.py tests/test_features.py
git commit -m "feat: score intrinsic decision importance"
```

### Task 11: Early Evidence-Backed Engineer Report and Analysis Checkpoint

**Files:**
- Create: `scripts/architecture_graph/report.py`
- Create: `scripts/architecture_graph/analysis.py`
- Modify: `scripts/architecture_graph/fingerprint.py`
- Modify: `scripts/architecture_graph/records.py`
- Modify: `scripts/architecture_graph/indexer.py`
- Modify: `scripts/architecture_graph/snapshot.py`
- Modify: `scripts/architecture_graph/query.py`
- Modify: `scripts/architecture_graph/cli.py`
- Create: `scripts/architecture_graph/review_commands.py`
- Modify: `tests/helpers/phase2_catalog.py`
- Modify: `tests/test_jsonl_store.py`
- Modify: `tests/test_phase1_cli.py`
- Modify: `tests/test_sources.py`
- Modify: `tests/test_snapshot.py`
- Create: `tests/test_report.py`
- Create: `tests/test_analysis_pipeline.py`

**Interfaces:**
- Produces: `RenderedReport(markdown, cited_claim_ids, cited_evidence_ids, derivation_ids)`.
- Produces: `render_engineer_report(selections: Mapping[LifecycleLens, ProjectionSelection], rankings, overspecification, config) -> RenderedReport`; current and review selections are required and each report section uses the exact lens mapping declared in Step 2.
- Produces: `AnalysisResult(provenance_layer, records_by_type, report)` and `snapshot_records()`; one result contains one content version per stable ID for one provenance layer.
- Produces interim `analyze_corpus_intrinsic(...) -> AnalysisResult` for the deterministic layer.
- Produces: `FrozenReviewSet(records, canonical_bytes, digest)`, where records are fully validated/stable-ID-sorted and the digest hashes the exact canonical bytes.
- Produces: `analyze_reviewed_catalog(parent_reader, frozen_review_set, ...) -> AnalysisResult` and `finalize_reviewed_snapshot(...) -> ReviewFinalizeResult` without modifying the parent snapshot; proposals come only from the immutable parent's `proposals.jsonl`. `ReviewFinalizeResult(snapshot_id, observation_id: str | None, reused)` is separate from Phase 1 `PublishedSnapshot`; only an unchanged reviewed no-op has null observation ID.
- Produces: `append_review(project, request, config) -> ReviewAppendResult`; `ReviewAppendRequest` carries an optional immutable `parent_snapshot_id` selector plus the bounded target/replacement/evidence payload and never supplies its own authority value. The function resolves and opens the explicit selector or current snapshot only after acquiring the project lock; callers cannot pass a pre-opened reader.
- Consumes: repaired Phase 1 `canonical.source_revision_digest(content_hashes: Iterable[str]) -> str`; callers pass selected `SourceInput.content_hash` values and Phase 2 introduces no second function with this name.
- Adds public CLI commands `architecture-graph review append ...` and `architecture-graph review finalize ...`.

- [ ] **Step 1: Write failing fixed-section and vertical-slice tests**

Create `tests/test_report.py`:

```python
from architecture_graph.analysis_types import LifecycleLens


def test_report_has_four_fixed_sections_and_auditable_items(report_fixture) -> None:
    rendered = render_engineer_report(
        report_fixture.selections,
        report_fixture.rankings,
        report_fixture.overspecification,
        ReportConfig(),
    )
    headings = [line for line in rendered.markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Current critical commitments",
        "## Cross-cutting consequences and risks",
        "## Contested, stale, or changing decisions",
        "## Possible over-specification and questions for the architect",
    ]
    assert "claim:adr-001:publish" in rendered.markdown
    assert "evidence:adr-001:publish" in rendered.markdown
    assert "producer: deterministic" in rendered.markdown
    assert "observed_at" not in rendered.markdown
    assert "current.json" not in rendered.markdown


def test_report_labels_stale_review_without_applying_it(report_fixture) -> None:
    selections = report_fixture.selections_with_stale_review
    rendered = render_engineer_report(
        selections,
        report_fixture.rankings,
        report_fixture.overspecification,
        ReportConfig(),
    )
    assert "review:stale-modality" in rendered.markdown
    assert "stale; not applied" in rendered.markdown
    assert selections[LifecycleLens.REVIEW].effective_status_by_target[
        ("claim", "claim:modality")
    ] == (
        "unreviewed"
    )
```

Create `tests/test_analysis_pipeline.py` using a real temporary Git fixture. Assert the published deterministic snapshot has nonempty terms, entities, claims, decisions, and rankings; all claim evidence/derivation references resolve; all diagnostic derivations resolve; and the persisted report is four-section content-only Markdown. Finalize the review fixture as a separate reviewed snapshot. Assert `snapshot_kind: reviewed`, `parent_snapshot_id` names the selected parent, `base_deterministic_snapshot_id` names the immutable deterministic base, `reviews.jsonl` equals the stable-ID-sorted canonical serialization of every record parsed from the locked ledger image, `frozen_review_set_digest` hashes those exact snapshot bytes, and the reviewed bundle contains one content version per stable ID. Reordering the valid external ledger without changing its records produces the same frozen digest; changing any record changes it. An accepted modality correction changes the reviewed decision digest/diagnostic/rank while the deterministic snapshot and base claim bytes remain unchanged; an accepted subject-identity correction leaves no dangling decision member or graph endpoint. An accepted canonical-predicate correction to a valid predicate absent from the parent materializes its controlled-predicate term, replaces the old claim-predicate edge, and passes complete snapshot reference validation.

Then append a second correction targeting the exact first reviewed successor digest and finalize again with current (the reviewed V1 snapshot) as parent. Assert reviewed V2 names reviewed V1 as parent, inherits the same deterministic base, retains the first accepted change exactly once, adds only the second successor step, resolves the complete frozen ledger, and leaves one content version per stable ID. A new review aimed at a displaced predecessor digest is stale/invalid and must instead target the selected successor.

Finalize reviewed V2 again without appending or changing authority/pipeline inputs. Assert the command returns `ReviewFinalizeResult(reviewed_v2_id, None, True)`, writes no staging directory or observation, and leaves `current.json` byte-identical. The CLI envelope contains the existing snapshot ID, `observation_id: null`, and `reused: true`. This prevents an unchanged ledger from creating an infinite reviewed-parent chain without violating Phase 1's non-null published-observation contract.

Add focused fingerprint tests: changing one byte in `reviews.py`, `projections.py`, the review-schema declarations, reviewed orchestration, or reviewed-report template changes `review_pipeline_digest`; changing an output-affecting dependency version changes it too. Finalization with a current deterministic fingerprint different from the selected parent's `deterministic_pipeline_digest` fails before reading/finalizing the review ledger, staging, observation append, or pointer update and instructs the caller to index a fresh deterministic base. A matching fingerprint publishes both exact digest/preimage pairs and reopening rejects a mutated preimage even when all payload files are intact.

Add CLI/integration tests that append a verify review against an exact target ID/content digest and assert the ledger record copies reviewer authority and policy digest from `.architecture-graph.yaml`. Construct a current-selected request, change `current.json` to another valid snapshot before the append function acquires its lock, and prove target resolution occurs against the newly selected snapshot under the lock; a target digest valid only in the stale snapshot fails without appending. An explicit immutable `parent_snapshot_id` remains exact. An unknown reviewer, stale target digest, malformed field/verdict shape, replacement over 64 KiB, more than 20 evidence IDs, an unknown evidence ID, or a supplied ID that resolves to a non-evidence record returns 2 and leaves ledger bytes unchanged. `review finalize` then publishes and selects a reviewed snapshot with the frozen ledger digest. `review --help`, `review append --help`, and `review finalize --help` expose the complete workflow; both success responses are small canonical envelopes.

Append two otherwise identical reviews at distinct fixed `--created-at` test times and assert both IDs coexist. Append a third review with `supersedes_review_id` naming the first and assert the reference resolves while the second remains independent. Repeating the exact same event/time deduplicates rather than corrupting the append-only ledger. Missing, cross-reviewer, incompatible-target/field, and cyclic supersession attempts each return 2 and preserve the ledger's exact prior bytes; the cycle fixture includes an otherwise well-shaped manually staged forward reference so closing it cannot repair-and-poison the ledger.

Assert every stored claim attached by the reducer has nonempty `decision_ids` and its reducer-selected applicability, and that no pre-reducer content digest for the same stable claim ID remains anywhere in `claims.jsonl`.

Also parameterize a valid analysis bundle with: a claim missing `segment_id`; a dangling or wrong-kind field-origin ID; a dangling proposal derivation; a review superseding a missing review; a decision with an unresolved external predecessor locator; a lineage predecessor with neither local nor external locator; a decision-analysis or decision-diagnostic warning naming a missing decision; a ranking input missing from the bundle; an edge with a missing endpoint; and an edge whose resolved endpoint kind violates `EDGE_ENDPOINT_KINDS`. `SnapshotFinalizer.validate()` must reject each mutation before staging or pointer changes. Publish one global model warning, one `decision_analysis` ambiguous-status warning, and one decision-diagnostic warning to prove all discriminated envelopes pass. Build a four-revision deterministic chain and prove an external history reference to the oldest reachable ancestor validates, while a locator to an unrelated snapshot fails.

Add source-revision tests over real `SourceInput` values while consuming the repaired Phase 1 helper. Assert both `revision_digest == source_revision_digest(item.content_hash for item in inputs)` and `revision_digest == sha256_digest(canonical_bytes(sorted({item.content_hash for item in inputs})))`; no object wrapper or Phase 2 helper is permitted. Pipeline, parser-model, scoring, alias, source-kind/role/authority, path, and report-only configuration changes keep that digest unchanged while changing `material_input_digest`. Adding a second selected path with byte-identical content at any authority also keeps the source-revision digest unchanged. When the bytes carry an explicit document ID, Phase 1 must accept the identical duplicate and assign both versions the same logical-source ID; reusing that explicit ID on different bytes must fail before publication. Adding, removing, or changing a unique byte group changes the revision digest. Deterministic manifests persist the exact digest; reviewed/enriched manifests inherit it from their immutable deterministic base. A query for `--provenance-layer deterministic` while current itself is deterministic opens current successfully rather than trying to dereference its null base field.

Phase 1 already requires and validates `source_revision_digest` in manifests, observations, and deterministic input identity. Preserve those fixtures and the canonical helper unchanged. Add only Phase 2 layered-inheritance/wrong-digest regressions plus exact empty, unique, and ambiguous rename preimage expectations, so extending the pipeline cannot drop or reshape Phase 1's existing `source_revision_digest` or `rename_resolution` inputs.

Add a real end-to-end duplicate-copy regression in `tests/test_analysis_pipeline.py`. Index a corpus containing one explicit-ID ADR, then add a second selected path with exactly the same bytes and an authority no lower than the original. The material snapshot changes and gains source/segment/evidence locations, but its source-revision digest stays fixed. Assert the set of claim IDs, every `claim_identity_payload`, decision semantic digests/statuses, semantic edge weights, feature vectors, scores, and rank order are unchanged; the affected claim canonical-unions both source-version/evidence/derivation sets instead of creating another ordinal. This exercises ingestion through final ranking and prevents a unit-only coalescing rule from drifting.

Run:

```bash
uv run pytest tests/test_report.py tests/test_analysis_pipeline.py -q
```

Expected: FAIL because report rendering and analysis orchestration do not exist.

- [ ] **Step 2: Implement content-only engineer report rendering**

Use the four exact headings above and require `selections` to contain both `LifecycleLens.CURRENT` and `LifecycleLens.REVIEW` for the snapshot's one provenance layer. Section one selects only from CURRENT and sorts by its stored criticality rank. Section two selects consequence/risk-bearing CURRENT decisions and also sorts by current criticality. Sections three and four select only from REVIEW and sort by stored review-priority rank; their displayed confidence is the review-lens confidence for the same decision. Historical rankings are persisted for bounded historical queries but never substituted into the report. Reject missing selections, mixed provenance layers, or a ranking whose lens/layer does not match its section. Within each section use decision ID as the final tie-breaker. Each item renders, in order: Decision; Status and scope; Why it ranks; Consequence; Evidence; Derivation; Confidence; Architect question. Empty sections contain `- None.`.

Only accepted current decisions enter section one. Section two requires a documented consequence/risk edge in the current selection. Section three contains conflict, absent/proposed/deprecated/disputed/changing review material plus explicit stale/invalid review annotations. `ProjectionSelection` carries immutable `stale_review_ids`, `invalid_review_ids`, and `disputed_targets` from `ReviewProjection`; the renderer never tries to infer these states from raw review records. A stale/invalid review is named and labeled not applied and cannot change effective status. Section four contains review-selection over-specification result flagged or unknown; unknown is labeled unassessed. Criticality, review priority, and confidence remain separate.

Every source-facing statement names claim and evidence IDs. Every score/conflict/omission/derivation statement names input and derivation IDs. Persist no snapshot ID, branch, commit, observation, publication time, or current-pointer state.

- [ ] **Step 3: Implement intrinsic orchestration and one publication path**

`analyze_corpus_intrinsic` accepts the validated `ProjectConfig` and calls in order: parse; terms; relation candidates; qualification of `claim_eligible_candidates`; entity resolution with the exact immutable `IngestedCorpus` plus `project_config.aliases`; claims; deterministic decisions; deterministic diagnostics; current/review/historical deterministic lifecycle projections; intrinsic features/retrieval; rankings; report from the required current/review selection map. Immediately after decision reduction it computes `final_claims = tuple(updated_claims_by_id.get(claim["id"], claim) for claim in original_claims)`, appends only explicitly new IDs, and asserts one content version per stable ID before building the deterministic catalog. It returns all fourteen record types for the deterministic layer, using canonical empty proposal/review files. Merge every `ParsedCorpus.derivations` record exactly once before resolving term/relation upstream provenance; deduplicate derivations/edges by stable ID and reject same-ID/different-digest collisions.

`analyze_reviewed_catalog` starts from one immutable deterministic, enriched, or reviewed parent reader and the validated, stable-ID-sorted review records parsed from one locked ledger image. It receives their exact canonical snapshot bytes/digest as identity inputs; it never treats the external append order as semantic. It loads proposals only from that parent's verified `proposals.jsonl`, so the parent's content digest covers every proposal byte; callers cannot inject a second proposal set. For a reviewed parent, scan its field origins, predecessor locators, and lineage to identify review/proposal events already materialized in that self-contained catalog. Preserve those successors exactly once, reduce the complete ledger for status/reporting, and apply only newly effective corrections/proposals that target an exact record version in the selected parent. An event targeting a displaced predecessor is stale and cannot undo/reapply an accepted successor; a follow-up must target the current successor digest. It then substitutes changed entity IDs through claims, reruns decision reduction and diagnostics, and runs the same projection/ranking/report tail over only the fully cascaded reviewed catalog. It copies unchanged parent records needed for a self-contained bundle, replaces same-ID successors, adds new identities and lineage, and never copies a replaced content version. The result's rankings all use `provenance_layer: reviewed`.

`finalize_reviewed_snapshot` publishes that result through the same validated writer with `snapshot_kind: reviewed`, `parent_snapshot_id` set to the immutable selected parent (including a reviewed parent), `base_deterministic_snapshot_id` inherited from the parent or set to the deterministic parent itself, no deterministic `analysis_parent_snapshot_id`, the deterministic base's `source_revision_digest`, the parent's material/deterministic pipeline digests, the review-pipeline digest, `review_authority_policy_digest`, and a reviewed input digest covering the parent (including its proposal ledger and already materialized successor state), base, canonical frozen review bytes, authority policy, and review pipeline. Ordering is strict under the project lock: resolve the selected parent/base; compute the current deterministic fingerprint from the parent's recorded runtime/model configuration and require exact equality with its inherited digest; compute the review fingerprint/policy input; only then read one review-ledger byte image, fully validate it, stable-ID-sort it, serialize it with the shared canonical writer, and hash those canonical bytes. A deterministic mismatch therefore fails before ledger read, analysis, staging, observation, or pointer work and cannot be bypassed by no-op reuse. After the verified frozen read, if the selected parent is reviewed and its frozen review-set digest, review-authority-policy digest, inherited deterministic digest, current review-pipeline digest, proposal digest, and set of already materialized review IDs exactly match current inputs, return `ReviewFinalizeResult(parent_id, None, True)` without an observation, staging, or pointer write. Otherwise analyze and publish, returning the normal non-null observation in `ReviewFinalizeResult`. A deterministic snapshot never contains reviewed successors. Phase 2 has no live enrichment command; if a future enriched parent exists, the same reviewed finalizer may consume it. Public read commands resolve a requested provenance layer to a concrete immutable snapshot: when the selected snapshot is deterministic, deterministic opens that snapshot itself; only an enriched/reviewed selection dereferences its non-null `base_deterministic_snapshot_id`. Reviewed requires a selected reviewed snapshot, and enriched requires a reachable enriched parent. Missing layers return an error instead of falling back.

`review_commands.append_review` accepts no reader. It acquires the outer project lock, then resolves `request.parent_snapshot_id` or reads current state and opens that immutable target while still holding the lock. It holds the lock across every preflight and `AtomicJsonlLedger.append` (whose Phase 1 contract requires the caller to own that lock). It requires the caller's exact target kind/ID/content digest to resolve there and every supplied evidence ID to resolve there with kind `evidence`. It loads the configured authority policy and looks up `reviewer_id`; no CLI flag can set authority. It validates the verdict/field/replacement shape, caps canonical replacement JSON at 65,536 characters and evidence IDs at 20, stamps an exact UTC `YYYY-MM-DDTHH:MM:SSZ` human event time, and validates it with `canonical_utc_event_time` before computing the replacement-value digest. Offset, fractional, missing, or invalid calendar spellings fail before ledger mutation. It sets the review ID by hashing reviewer ID, exact target locator, field path, verdict, replacement digest, sorted evidence IDs, authority-policy digest, superseded review ID, and event time. Under the same lock it parses and fully validates the existing homogeneous ledger. A non-null superseded ID must resolve there, belong to the same reviewer, use the same target kind/stable ID and field path (the content digest may be an earlier same-ID version), and leave the complete supersession graph acyclic. Exact duplicate events deduplicate; distinct event times or valid supersession links produce distinct IDs. Only after all checks does it finalize the review record and perform crash-safe replacement. `review finalize` selects an explicit `--parent` or current snapshot and invokes the lock-aware reviewed finalizer. Expected validation/state errors map to exit 2 without changing ledger bytes, staging, observation, or pointer state.

The reviewed finalizer uses the same project lock as `AtomicJsonlLedger`. While holding it, it reads and validates one byte image of `reviews/reviews.jsonl`, canonical-sorts the parsed records, computes `frozen_review_set_digest` from the exact bytes destined for snapshot `reviews.jsonl`, builds and validates the reviewed staging bundle, publishes it, appends its observation, and updates `current.json`. Expose a lock-aware internal publisher to avoid nested acquisition. A concurrent review append therefore runs either before the frozen read and enters the snapshot, or after the current-pointer update and remains pending for the next reviewed snapshot. Add a concurrency test that blocks finalization at the frozen read, attempts an append, and proves the append cannot commit between canonical frozen-digest computation and publication.

Extend `SnapshotBundle`, `SnapshotWriter.create`, manifest-core validation, and manifest serialization only with nullable digest/preimage pairs `enrichment_pipeline_digest`/`enrichment_pipeline_fingerprint` and `review_pipeline_digest`/`review_pipeline_fingerprint`, plus nullable `review_authority_policy_digest`. Preserve Phase 1's existing required `source_revision_digest` field and independent validation unchanged. The existing Phase 1 `pipeline_fingerprint` remains the exact deterministic preimage and every layer inherits it unchanged. Deterministic bundles compute the source revision through `canonical.source_revision_digest` and set all enrichment/review fields null. Every layered bundle must equal the source-revision digest and deterministic fingerprint/digest of its declared deterministic base. Reviewed bundles require a review digest, a canonical review fingerprint whose hash equals that digest, and an authority-policy digest; they inherit the enrichment digest/preimage pair only when their declared ancestry contains an enriched parent, and otherwise require both null. An enriched bundle follows the symmetric rule for its enrichment pair. Keep these fields inside manifest and snapshot identity; do not place them on individual records.

Reuse the Phase 1 observation required-field/schema validator and its new/reused observation constructors without redefining `source_revision_digest`. Layered publication copies that value from the verified deterministic base and requires it to equal the selected snapshot manifest's value. Add layered round-trip and mismatch tests; no observation or layered finalizer may synthesize a different revision key.

Add `review_pipeline_fingerprint(parent_deterministic_digest)` beside `pipeline_fingerprint`. Its canonical stage manifest names and hashes `schemas.py` review variants, `reviews.py`, `projections.py`, reviewed orchestration in `analysis.py`, reviewed publication in `indexer.py`/`snapshot.py`, and reviewed report code/templates; it also includes the parent deterministic digest, Python runtime, and exact output-affecting dependency versions. Development checkouts hash those files/resources; packaged builds hash the installed artifact plus the same stage manifest. Persist this exact canonical preimage as `review_pipeline_fingerprint` and validate its hash before reuse or publication, just as Phase 1 validates `pipeline_fingerprint`. Authority values and canonical frozen review bytes belong to reviewed input identity, not pipeline identity.

Wire Phase 2 validation into the shared publication path: `_deduplicate` invokes `validate_typed_record` for every known Phase 2 kind and aggregates all issues; `SnapshotFinalizer.validate` then invokes `validate_snapshot_references`. The external resolver starts only from the bundle's declared parent, base, and analysis-parent locators, opens and verifies each immutable manifest/payload, and may follow their declared parent/base/analysis-parent links recursively. It rejects a snapshot locator outside that verified ancestry. This permits multi-revision history without accepting arbitrary project snapshots. No `write_stage`, reuse, or pointer update runs after a typed/reference error.

Do not add or shadow `source_revision_digest` in `sources.py`. Compute it only with `canonical.source_revision_digest(item.content_hash for item in inputs)`. Its sole preimage remains Phase 1's canonical array `sorted(set(content_hashes))`; never wrap that array in a Phase 2 object. Paths, multiplicity, source kind/role/authority, tracking metadata, pipeline/model/runtime identity, scoring, ontology, aliases, and report configuration remain excluded by the existing helper. Any byte-identical copy therefore leaves the revision key unchanged regardless of path-derived metadata. Authority aggregation remains the separate conservative content-group rule used by reducers/scorers.

Change `pipeline_fingerprint` to accept the already loaded `NlpRuntime` identity and cover every Phase 2 Python module/resource, installed spaCy/scikit-learn version, configured bounded model artifact digest, the `ModelArtifactLimits` constants, and report code. Index order is exact: load config and discover sources; compute `canonical.source_revision_digest(item.content_hash for item in inputs)`; load the installed/no-download runtime through the sole confined/regular-file/no-symlink/capped artifact routine from Task 2; fingerprint code, dependency versions, and that runtime artifact; compute material digest; perform unchanged observation-only reuse; then parse/analyze only when material changed. `memory_status` uses that identical runtime loader, artifact limits, and canonical source-revision helper, so freshness and indexing either produce the same digests or the same visible artifact-limit error. Preserve Phase 1's deterministic `input_digest` canonical payload exactly: `material_input_digest`, `source_revision_digest`, `analysis_parent_snapshot_id`, and `rename_resolution.as_digest_input()`. Add an exact-preimage test for an empty resolution, a unique rename, and an ambiguous rename. This removes any circularity between parser provenance and pipeline identity while ensuring a changed installed model invalidates reuse without pretending the documents changed. `index_repository` constructs `IngestedCorpus`, invokes analysis, merges Phase 1 records plus all `ParsedCorpus.warnings`, all `ParsedCorpus.derivations`, and all Phase 2 results, then publishes one `SnapshotBundle`. Extend `IndexResult`/CLI JSON with claim and decision counts.

- [ ] **Step 4: Run the early report checkpoint**

```bash
uv run pytest tests/test_report.py tests/test_analysis_pipeline.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: the entire suite passes; the fixture produces an evidence-backed report before centrality, history, or semantic diff exists.

- [ ] **Step 5: Commit the early checkpoint**

```bash
git add scripts/architecture_graph/report.py scripts/architecture_graph/analysis.py scripts/architecture_graph/review_commands.py scripts/architecture_graph/fingerprint.py scripts/architecture_graph/records.py scripts/architecture_graph/indexer.py scripts/architecture_graph/snapshot.py scripts/architecture_graph/query.py scripts/architecture_graph/cli.py tests/helpers/phase2_catalog.py tests/test_jsonl_store.py tests/test_phase1_cli.py tests/test_sources.py tests/test_snapshot.py tests/test_report.py tests/test_analysis_pipeline.py
git commit -m "feat: publish evidence-backed decision reports"
```

### Task 12: Evidence Graph and Semantic Ranking Projection

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `scripts/architecture_graph/fingerprint.py`
- Create: `scripts/architecture_graph/semantic_graph.py`
- Modify: `scripts/architecture_graph/analysis.py`
- Create: `tests/helpers/ranking_graphs.py`
- Create: `tests/test_semantic_graph.py`

**Interfaces:**
- Produces: `EvidenceGraph(nodes, edges)` and `SemanticProjection(nodes, edges, decision_node_ids, personalization_node_ids, digest)`.
- Produces: `build_evidence_graph(catalog, selection, configuration_digest, pipeline_digest) -> GraphProjectionResult`.
- Produces: `project_semantic_graph(evidence_graph, selection, config, derivation_id) -> SemanticProjection`.
- `GraphProjectionResult` contains the projection, every persisted graph edge, and the graph-rule derivation they cite.

- [ ] **Step 1: Write failing eligibility, direction, aggregation, and provenance tests**

Create `tests/test_semantic_graph.py` with accepted duplicate source claims, rejected/disputed claims, literal and unresolved arguments, differing scopes, and historical intervals:

```python
def test_semantic_projection_is_directional_aggregated_and_evidence_backed(
    semantic_fixture,
) -> None:
    result = semantic_fixture.project_current()
    edge = next(item for item in result.projection.edges if item.edge_type == "PUBLISHES_TO")
    assert (edge.from_id, edge.to_id) == ("entity:checkout", "entity:order-placed")
    assert edge.claim_ids == ("claim:publish-a", "claim:publish-b")
    assert edge.independent_source_count == 2
    assert all(
        not (item.from_id == "entity:order-placed" and item.to_id == "entity:checkout")
        for item in result.projection.edges
    )
    assert all("claim:literal-retention" not in item.claim_ids for item in result.projection.edges)
    assert all("claim:disputed" not in item.claim_ids for item in result.projection.edges)
    persisted = {item["id"] for item in result.derivations}
    assert all(set(item["derivation_ids"]) <= persisted | semantic_fixture.upstream_derivations for item in result.persisted_edges)
    assert all(
        semantic_fixture.endpoint_kind(item["from_id"])
        in EDGE_ENDPOINT_KINDS[item["edge_type"]][0]
        and semantic_fixture.endpoint_kind(item["to_id"])
        in EDGE_ENDPOINT_KINDS[item["edge_type"]][1]
        for item in result.persisted_edges
    )
    node_ids = {item.id for item in result.evidence_graph.nodes}
    assert {
        endpoint
        for item in result.persisted_edges
        for endpoint in (item["from_id"], item["to_id"])
    } <= node_ids


def test_negative_claim_never_emits_its_positive_relationship(semantic_fixture) -> None:
    result = semantic_fixture.project_negative_call(
        modality="must", polarity="negative"
    )
    assert not any(
        item.edge_type == "CALLS"
        and item.from_id == "entity:checkout"
        and item.to_id == "entity:legacy"
        for item in result.projection.edges
    )
    prohibition = next(
        item for item in result.projection.edges
        if item.edge_type == "PROHIBITS"
    )
    assert prohibition.edge_discriminator == {"prohibited_predicate": "calls"}
    assert prohibition.claim_ids == ("claim:must-not-call",)


def test_prohibitions_over_same_endpoints_keep_predicate_discriminator(
    semantic_fixture,
) -> None:
    result = semantic_fixture.project_negative_relationships(
        predicates=("calls", "reads_from")
    )
    prohibitions = [
        item for item in result.persisted_edges
        if item["edge_type"] == "PROHIBITS"
    ]
    assert len(prohibitions) == 2
    assert len({item["id"] for item in prohibitions}) == 2
    assert {item["edge_discriminator"]["prohibited_predicate"] for item in prohibitions} == {
        "calls",
        "reads_from",
    }
    native = semantic_fixture.project_native_prohibits()
    native_edge = next(
        item for item in native.persisted_edges
        if item["edge_type"] == "PROHIBITS"
    )
    assert native_edge["edge_discriminator"] == {
        "prohibited_predicate": "prohibits"
    }


def test_scope_prevents_aggregation_and_lenses_change_eligibility(semantic_fixture) -> None:
    current = semantic_fixture.project("current", "deterministic")
    review = semantic_fixture.project("review", "enriched")
    historical = semantic_fixture.project("historical", "reviewed")
    assert len(current.projection.edges) < len(review.projection.edges)
    assert historical.projection.digest != current.projection.digest
    production = [
        item for item in review.projection.edges if item.normalized_scope == {"environments": ("production",)}
    ]
    staging = [
        item for item in review.projection.edges if item.normalized_scope == {"environments": ("staging",)}
    ]
    assert production and staging


def test_projection_aggregates_are_ephemeral_and_durable_edges_do_not_collide(
    semantic_fixture,
) -> None:
    current = semantic_fixture.project("current", "deterministic")
    review = semantic_fixture.project("review", "deterministic")
    assert current.projection.edges != review.projection.edges
    durable = current.persisted_edges
    assert durable == review.persisted_edges
    assert len({item["id"] for item in durable}) == len(durable)


@pytest.mark.parametrize("change_shape", ["same_id", "new_id"])
def test_reviewed_graph_omits_edges_to_replaced_predecessor_versions(
    semantic_fixture, change_shape: str
) -> None:
    result = semantic_fixture.project_reviewed_successor(change_shape)
    local_versions = {
        (item["kind"], item["id"], item["content_digest"])
        for item in result.catalog.records
    }
    assert all(
        edge["edge_type"] not in {"PROPOSES", "REVIEW_OF"}
        or semantic_fixture.edge_target_locator(edge) in local_versions
        for edge in result.persisted_edges
    )
    assert result.target_records_resolve_through_verified_ancestry is True


def test_networkx_version_participates_in_pipeline_and_graph_derivation(
    semantic_fixture, monkeypatch
) -> None:
    first = semantic_fixture.pipeline_fingerprint(networkx_version="3.6.1")
    second = semantic_fixture.pipeline_fingerprint(networkx_version="3.6.2")
    assert first.digest != second.digest
    result = semantic_fixture.project_current()
    assert result.derivations[0]["tool_version"] == semantic_fixture.networkx_version
```

Run:

```bash
uv run pytest tests/test_semantic_graph.py -q
```

Expected: FAIL because semantic graph projection does not exist.

- [ ] **Step 2: Add NetworkX while retaining JSONL as canonical state**

Add once to `[project].dependencies`:

```toml
"networkx>=3.6,<4",
```

Run:

```bash
uv lock
uv sync
```

Expected: NetworkX is locked; no database or provider SDK is added.

Add NetworkX's observed distribution version to the deterministic dependency manifest in `fingerprint.py`; graph-rule derivations record that same version. A dependency version change must change the pipeline digest even when source files and scoring JSON are unchanged.

- [ ] **Step 3: Build the reified evidence graph**

Reify only records that already live in the fourteen JSONL ledgers: entity, term, claim, decision, evidence, source, derivation, proposal, and review. Durable edge records are not graph nodes; their provenance remains directly in `edge.derivation_ids`, so an edge can never be the source of `DERIVED_FROM`. Concerns are `entity_type: concern`; consequences are `entity_type: consequence` or claims with role consequence; controlled predicates are Task 6 `term_kind: controlled_predicate` records. Emit only edge types in `EDGE_ENDPOINT_KINDS`: claim subject/predicate/object, membership, evidence, derivation, support/conflict/supersession, driver, consequence, governs, affects, proposal, and review edges. Apply the polarity rule when emitting durable entity relationship edges too, so the evidence graph never persists a positive edge for a negative claim. Emit CLAIM_SUBJECT and CLAIM_OBJECT only for `entity_ref`; implicit/unresolved/literal arguments remain inside their claim and do not create graph endpoints. Emit `PROPOSES` or `REVIEW_OF` only when the target's exact kind, ID, and content digest exists in the local catalog. When an accepted same-ID or identity-changing successor displaced that exact predecessor version, retain the immutable target locator on the proposal/review and resolve it through verified ancestry for validation/reporting, but omit the graph edge rather than pointing at a different version. Every durable endpoint resolves to an allowed constructed node before the graph is returned. All durable edges retain sorted evidence, input, and derivation IDs. Synthetic edges cite the returned graph-rule derivation; copied upstream edges retain their upstream derivations.

`edges.jsonl` stores this projection-independent evidence graph once per snapshot. If multiple claims establish the same durable entity relationship, aggregate their claim/evidence/derivation IDs across the snapshot's one catalog without applying a lifecycle or provenance selector. Durable edge identity is edge type, endpoints, canonical scope, effective time, and the typed `edge_discriminator` (empty except for the original predicate on `PROHIBITS`). It never stores projection weight, eligible-claim subset, lens, layer, rank, or selector state.

- [ ] **Step 4: Apply lifecycle/provenance eligibility and semantic aggregation**

Current includes accepted, verified/unreviewed decisions and active selected claims; maintained observations need confidence at least 0.50 or human verification. Review adds absent/proposed/deprecated/disputed decisions, but rejected/disputed claims remain diagnostic only. Historical includes every decision captured by the selected snapshot; non-rejected, non-disputed assertion claims may emit edges and retain effective intervals as edge metadata. V1 exposes no arbitrary time-point selector.

Polarity gates semantic relationships before aggregation. A positive entity-ref claim emits its canonical predicate; a native positive `prohibits` claim uses `edge_discriminator: {"prohibited_predicate": "prohibits"}`. A negative must/should claim whose canonical predicate is not already `prohibits` emits `PROHIBITS`, with the original predicate stored as `edge_discriminator.prohibited_predicate` and included in edge identity/aggregation. Other negative claims remain reified but emit no positive or inferred semantic relationship. Thus `must not call` can never add `CALLS`; a negative `prohibits` claim is left reified because its logical inverse is not inferred. Every `PROHIBITS` edge, native or rewritten, therefore satisfies the same nonempty discriminator schema.

Only entity-ref subject/object claims emit directed subject→object semantic assertions. Never emit inverses. Literal, unresolved, and implicit arguments remain reified but centrality-ineligible. Add exact decision relationships GOVERNS, ADDRESSES, JUSTIFIED_BY, HAS_CONSEQUENCE, and AFFECTS only when supporting claims establish them.

Build semantic aggregates in memory from the durable evidence graph and selected catalog. Aggregate only on from, edge type, to, canonical scope, effective-time interval, and edge-type discriminators such as `prohibited_predicate`. Retain the eligible claims/evidence/derivations in the ephemeral `SemanticEdge`; do not finalize or append these aggregates to `edges.jsonl`. Transition weight is base weight × evidence-weighted extraction confidence × decision status factor × `min(1, independent sources / 3)`; unattached maintained observations use 0.65 status factor. Personalization contains sorted concerns/constraints of accepted decisions plus interface, data-boundary, and shared-infrastructure nodes; empty means uniform later. Projection digest hashes canonical nodes, semantic aggregates, lifecycle/provenance selectors, scoring digest, and graph derivation. Queries reconstruct only the requested bounded semantic projection from the projection-independent records.

- [ ] **Step 5: Run focused and cumulative tests**

```bash
uv run pytest tests/test_semantic_graph.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: focused and cumulative tests pass; durable graph records cite only persisted derivations.

- [ ] **Step 6: Commit graph projection**

```bash
git add pyproject.toml uv.lock scripts/architecture_graph/fingerprint.py scripts/architecture_graph/semantic_graph.py scripts/architecture_graph/analysis.py tests/helpers/ranking_graphs.py tests/test_semantic_graph.py
git commit -m "feat: build typed architecture graph projections"
```

### Task 13: Deterministic Decision Lineage, Persistence, and Churn

**Files:**
- Create: `scripts/architecture_graph/history.py`
- Create: `tests/helpers/history_snapshots.py`
- Create: `tests/test_history.py`

**Interfaces:**
- Produces: `infer_source_lineage(previous_sources, current_sources, derivation_id, previous_snapshot_id) -> tuple[Record, ...]`.
- Produces: `match_decision_predecessors(previous, current, source_lineage, jaccard_threshold=0.80) -> tuple[DecisionLineageMatch, ...]`.
- Produces: `infer_decision_lineage(previous, current, source_lineage, derivation_id, jaccard_threshold=0.80) -> tuple[Record, ...]`.
- Produces: `DecisionHistory.metrics_for(decision, current_lineage) -> HistoryFeatures`.
- Produces: `inherit_history_features(successor, review_lineage, base_history) -> HistoryFeatures` for enriched/reviewed layers.
- Produces: `load_decision_history(project: ProjectPaths, parent_snapshot_id: str | None, current_source_revision_digest: str, *, persistence_transitions: int = 5, churn_transitions: int = 3, traversal_safety_limit: int = 100) -> DecisionHistory`; this function performs verified immutable ancestor reads only and emits no durable record.
- Produces: `apply_decision_history(history: DecisionHistory, current_catalog: RecordCatalog, *, configuration_digest: str, pipeline_digest: str, jaccard_threshold: float = 0.80) -> HistoryResult`; this function exclusively owns current source/decision matching, lineage derivations, predecessor locators, and current decision finalization.
- `HistoryResult` contains source and decision lineage, the supplied/advanced history, updated decisions, and both persisted deterministic lineage derivations.

- [ ] **Step 1: Write failing match-order, tie, persistence, and churn tests**

Create `tests/test_history.py`:

```python
def test_lineage_uses_the_approved_match_order() -> None:
    previous, current = ordered_lineage_candidates()
    result = infer_decision_lineage(
        previous,
        current,
        (),
        "derivation:history",
        jaccard_threshold=0.80,
    )
    assert [(item["predecessor_id"], item["successor_id"], item["reason"]) for item in result] == [
        ("decision:old-explicit", "decision:new-explicit", "explicit_identifier"),
        ("decision:old-heading", "decision:new-heading", "logical_source_heading"),
        ("decision:old-overlap", "decision:new-overlap", "claim_key_jaccard"),
        ("decision:old-primary", "decision:new-primary", "primary_claim_key"),
    ]


def test_source_versions_link_only_through_phase1_logical_identity() -> None:
    previous, current = renamed_source_versions()
    lineage = infer_source_lineage(
        previous,
        current,
        "derivation:history",
        "deterministic:" + "a" * 64,
    )
    assert [(item["predecessor_id"], item["successor_id"]) for item in lineage] == [
        ("source:old-runtime", "source:new-runtime")
    ]
    ambiguous_previous, ambiguous_current = ambiguous_source_versions()
    assert infer_source_lineage(
        ambiguous_previous,
        ambiguous_current,
        "derivation:history",
        "deterministic:" + "a" * 64,
    ) == ()


def test_tied_jaccard_candidates_are_add_remove_not_lineage() -> None:
    previous, current = tied_lineage_candidates()
    assert infer_decision_lineage(previous, current, (), "derivation:history") == ()


def test_persistence_counts_deterministic_revisions_not_observations(tmp_path) -> None:
    fixture = history_project(
        tmp_path,
        semantic_digests=(
            "sha256:" + "c" * 64,
            "sha256:" + "c" * 64,
            "sha256:" + "c" * 64,
        ),
        observations_per_snapshot=(3, 1, 4),
    )
    history = load_decision_history(
        fixture.project,
        fixture.parent_snapshot_id,
        fixture.current_source_revision_digest,
    )
    result = apply_decision_history(
        history,
        fixture.current_catalog,
        configuration_digest="sha256:" + "d" * 64,
        pipeline_digest="sha256:" + "e" * 64,
    )
    metrics = result.history.metrics_for(fixture.current_decision, fixture.current_lineage)
    assert metrics.persistence_across_snapshots == 0.8
    assert metrics.churn == 0.0


def test_semantic_change_resets_persistence_and_increments_churn(tmp_path) -> None:
    fixture = history_project(
        tmp_path,
        semantic_digests=(
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
            "sha256:" + "2" * 64,
        ),
        observations_per_snapshot=(1, 1, 1),
        current_digest="sha256:" + "3" * 64,
    )
    result = fixture.load()
    metrics = result.history.metrics_for(fixture.current_decision, ())
    assert metrics.persistence_across_snapshots == 0.5
    assert metrics.churn == 2.0 / 3.0


def test_pipeline_and_config_rebuilds_inherit_one_source_revision(tmp_path) -> None:
    fixture = history_project(
        tmp_path,
        source_revision_digests=(
            "sha256:" + "a" * 64,
            "sha256:" + "b" * 64,
            "sha256:" + "b" * 64,
        ),
        semantic_digests=(
            "sha256:" + "c" * 64,
            "sha256:" + "c" * 64,
            "sha256:" + "d" * 64,
        ),
        rebuild_reasons=(None, None, "pipeline_and_config"),
    )
    before = fixture.metrics_at(1)
    after = fixture.metrics_at(2)
    assert after == before
    assert after.persistence_across_snapshots == 0.6
    assert after.churn == 0.0


def test_duplicate_path_rebuild_does_not_advance_or_hide_history(tmp_path) -> None:
    fixture = history_project(
        tmp_path,
        unique_source_revisions=6,
        same_revision_rebuilds_between_last_two=12,
        last_rebuild_adds_only_duplicate_path=True,
    )
    result = fixture.load(traversal_safety_limit=100)
    assert result.history.source_revision_digests == fixture.last_five_unique_digests
    assert result.history.metrics_for(
        fixture.current_decision, fixture.current_lineage
    ) == fixture.metrics_before_duplicate_path


def test_matched_decision_records_external_predecessor_but_genesis_is_null(
    tmp_path,
) -> None:
    fixture = history_project(tmp_path, with_matched_successor=True)
    result = fixture.load()
    updated = result.updated_decisions_by_id[fixture.current_decision["id"]]
    assert updated["predecessor_identity"] == {
        "snapshot_id": fixture.parent_snapshot_id,
        "record_id": fixture.previous_decision["id"],
        "content_digest": fixture.previous_decision["content_digest"],
        "reason": "explicit_identifier",
    }
    assert fixture.genesis_result.updated_decisions_by_id[
        fixture.genesis_decision["id"]
    ]["predecessor_identity"] is None


def test_lineage_derivations_are_acyclic_and_successor_digest_is_final(tmp_path) -> None:
    fixture = history_project(tmp_path, with_matched_successor=True)
    result = fixture.load()
    source_derivation = next(
        item for item in result.derivations
        if item["method"] == "source_lineage"
    )
    history_derivation = next(
        item for item in result.derivations
        if item["method"] == "decision_history"
    )
    source_lineage_ids = {item["id"] for item in result.source_lineage}
    assert source_lineage_ids.isdisjoint(source_derivation["input_ids"])
    assert source_lineage_ids <= set(history_derivation["input_ids"])
    updated = result.updated_decisions_by_id[fixture.current_decision["id"]]
    assert updated["id"] not in history_derivation["input_ids"]
    assert history_derivation["id"] in updated["derivation_ids"]
    decision_lineage = next(
        item for item in result.lineage
        if item["successor_id"] == updated["id"]
    )
    assert decision_lineage["successor_content_digest"] == updated["content_digest"]


def test_reviewed_successor_inherits_base_persistence_and_churn(tmp_path) -> None:
    fixture = history_project(tmp_path, with_reviewed_identity_change=True)
    inherited = inherit_history_features(
        fixture.reviewed_decision,
        fixture.review_lineage,
        fixture.base_history,
    )
    assert inherited == fixture.base_history.metrics_for(
        fixture.base_decision, fixture.base_lineage
    )
    assert fixture.reviewed_decision["semantic_digest"] != fixture.base_decision[
        "semantic_digest"
    ]
```

`history_project` writes only syntactically valid `sha256:` plus 64-lowercase-hex digests. Its `fixture.load()` helper is exactly the composition of `load_decision_history(...)` followed by `apply_decision_history(..., fixture.current_catalog, ...)`; it never hides a second matching or finalization path.

Run:

```bash
uv run pytest tests/test_history.py -q
```

Expected: FAIL because deterministic decision history does not exist.

- [ ] **Step 2: Implement ordered unique lineage matching**

`apply_decision_history` reads current sources, decisions, member claims, and reducer derivations only from its one `current_catalog`. First create a source-lineage derivation whose local inputs are sorted current source IDs and whose external inputs are the exact prior source locators already verified in `DecisionHistory`. It does not name any lineage record. Link a previous and current source version only when their Phase 1 `logical_source_id` is equal and unique on both sides. This consumes the explicit document ID, persistent path mapping, or unique Git-rename decision already recorded by Phase 1; Phase 2 never guesses a rename from prose similarity. A source tie emits no lineage. Its predecessor locator names the verified parent snapshot and content digest; successor is local. Source-lineage records cite only this source-lineage derivation.

Then match unmatched decisions in order: exact explicit decision/ADR ID; exact logical-source ID plus normalized heading; unique exact primary claim key in same logical source; unique predecessor at least 0.80 Jaccard across canonical claim keys. At each stage require unique predecessor and successor. Any tie emits no lineage. `match_decision_predecessors` returns immutable match descriptors before it creates records. Create a separate decision-history derivation whose local inputs are the sorted durable member-claim IDs, current source IDs, decision-reducer derivation IDs, and already materialized source-lineage IDs that produced the provisional decisions; provisional/current output decision IDs are never inputs because that version is not persisted. External inputs are the matched prior decision locators. The derivation never takes a decision-lineage record as input. Its output identity key may name sorted successor identity keys without treating them as input records. Identity hashes predecessor ID/digest and external snapshot locator, finalized successor identity key, reason, and the decision-history derivation. Sort by predecessor then successor.

- [ ] **Step 3: Load verified parent revisions, then apply them once to the current catalog**

`load_decision_history` resolves an enriched/reviewed start to `base_deterministic_snapshot_id`; a deterministic start is already its own base. It follows `analysis_parent_snapshot_id`, verifies every immutable manifest/payload it opens, and groups adjacent deterministic manifests by equal required `source_revision_digest`. Keep only the nearest (newest) snapshot as the representative of each completed group, continue until five distinct source revisions are collected, and enforce a separate default traversal safety limit of 100 verified manifests so rebuilds cannot hide older revisions or cause unbounded reads. The returned frozen `DecisionHistory` owns those verified ancestor snapshots, locators, and prior metrics; the loader creates no derivation, lineage, warning, successor, or other durable record. Never use observation count or raw deterministic snapshot count for persistence/churn.

The caller supplies the current build's source-revision digest to the loader because it is not published yet. After deterministic decision reduction, `analyze_corpus` calls `apply_decision_history` exactly once with the complete provisional `RecordCatalog`. If the digest equals the immediate deterministic parent's digest, the apply step matches current decisions to that parent and inherits their history features exactly; it does not compare the current semantic digest, reset persistence, add churn, or create another transition. The rebuilt snapshot becomes the newest representative for that group only after publication. New decisions with no unique predecessor begin with explicit unknown/initial history, not fabricated persistence. Pipeline, model, ontology, scoring, report, path/role/authority, and duplicate-copy-only changes can therefore rebuild outputs without becoming architecture-document revisions.

Persistence starts 0.50, adds 0.10 for each prior consecutive accepted/active revision with identical semantic digest, and caps at 1.00. A semantic change breaks the run. Churn is `min(1, changed semantic transitions across current plus last three deterministic transitions / 3)`. Rejected/superseded is inactive. The decision-history derivation `input_ids` contain only durable current member claims, sources, reducer derivations, and source-lineage records that resolve inside the output bundle; they are disjoint from every updated decision ID. Each prior decision input uses an `ExternalRecordRef` containing its parent snapshot, kind, stable ID, and content digest; the ordered external references participate in derivation identity and are verified by reopening those immutable parent snapshots. Snapshot IDs are therefore never smuggled into the local `input_ids` namespace.

For each match descriptor, `apply_decision_history` adds the typed `{snapshot_id, record_id, content_digest, reason}` predecessor locator and the decision-history derivation ID to the current decision, then finalizes that same-ID successor and recomputes its content digest. Only after finalization may it create the decision-lineage record, whose `successor_content_digest` must equal the successor that will be published. Return those successors in `HistoryResult.updated_decisions_by_id`. Genesis decisions retain explicit null. Task 14 replaces the pre-history decision version with this successor before ranking, reporting, and publication; it never appends both versions. No other function infers current lineage or finalizes history successors.

Only distinct deterministic source-revision groups advance persistence or churn. When an enriched or reviewed snapshot ranks a successor, `inherit_history_features` follows its unique accepted-successor lineage, including an identity-changing decision lineage, back to the base deterministic decision and returns that base position's history features. A same-ID successor uses its external predecessor locator; a new-ID successor uses the reviewed lineage record. Missing or ambiguous base lineage yields explicit unknown history inputs rather than treating the review correction as a source revision. A reviewed semantic correction may change authority, modality, impact, diagnostics, structure, and final score, but it cannot reset persistence or increment churn.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_history.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: focused and cumulative tests pass.

- [ ] **Step 5: Commit deterministic history**

```bash
git add scripts/architecture_graph/history.py tests/helpers/history_snapshots.py tests/test_history.py
git commit -m "feat: track deterministic decision history"
```

### Task 14: Structural Metrics and Final Rankings

**Files:**
- Modify: `scripts/architecture_graph/ranking.py`
- Modify: `scripts/architecture_graph/analysis.py`
- Modify: `scripts/architecture_graph/indexer.py`
- Modify: `tests/helpers/ranking_graphs.py`
- Create: `tests/test_ranking.py`
- Modify: `tests/test_analysis_pipeline.py`

**Interfaces:**
- Produces: `select_bridge_sample(node_ids, sample_size) -> tuple[str, ...]`.
- Produces: `compute_structural_features(projection, config) -> Mapping[str, StructuralDecisionFeatures]`.
- Produces: `rank_decisions(..., configuration_digest, pipeline_digest) -> RankingResult`.
- Produces final `analyze_corpus(..., project_config: ProjectConfig, history: DecisionHistory, configuration_digest: str, pipeline_digest: str, proposals=(), reviews=()) -> AnalysisResult`; prior decisions/source lineage are owned by `DecisionHistory` and are not separate arguments.

- [ ] **Step 1: Write failing metric, sampling, normalization, and final-score tests**

Create `tests/test_ranking.py`:

```python
from hashlib import sha256


def test_structural_features_are_typed_normalized_and_deterministic() -> None:
    values = compute_structural_features(bridge_projection(), ScoringConfig.load_v1())
    assert values["decision:bridge"].typed_personalized_pagerank == 1.0
    assert values["decision:bridge"].capped_bridge_score == 1.0
    assert all(0.0 <= value.structural_leverage <= 1.0 for value in values.values())


def test_constant_metrics_normalize_to_zero() -> None:
    values = compute_structural_features(
        bridge_projection(constant=True), ScoringConfig.load_v1()
    )
    assert {item.typed_personalized_pagerank for item in values.values()} == {0.0}
    assert {item.confidence_weighted_degree for item in values.values()} == {0.0}


def test_large_graph_bridge_sample_is_hash_sorted_and_fixed() -> None:
    node_ids = tuple(f"node:{index}" for index in range(5001))
    expected = tuple(
        sorted(node_ids, key=lambda value: sha256(value.encode("utf-8")).hexdigest())[:256]
    )
    assert select_bridge_sample(node_ids, 256) == expected


def test_final_scores_insert_structure_persistence_and_churn(ranking_fixture) -> None:
    result = ranking_fixture.rank()
    record = next(item for item in result.rankings if item["decision_id"] == "decision:bridge")
    assert record["ranking_phase"] == "final"
    assert record["features"]["persistence_across_snapshots"] == 0.7
    assert record["features"]["churn"] == 1.0 / 3.0
    assert record["semantic_projection_digest"] == ranking_fixture.projection_digest
    assert record["scores"]["criticality"] != record["scores"]["review_priority"]


def test_final_rankings_cover_all_lenses_for_the_snapshot_layer(ranking_fixture) -> None:
    result = ranking_fixture.rank_all()
    assert {
        (item["lifecycle_lens"], item["provenance_layer"])
        for item in result.rankings
    } == {
        (lens, ranking_fixture.provenance_layer)
        for lens in ("current", "review", "historical")
    }


def test_duplicate_source_bytes_at_higher_authority_do_not_inflate_any_rank(
    ranking_fixture,
) -> None:
    baseline = ranking_fixture.rank_with_duplicate_source(False)
    duplicated = ranking_fixture.rank_with_duplicate_source(
        True,
        duplicate_authority="accepted_adr_or_active_standard",
        original_authority="narrative_note",
    )
    assert duplicated.term["mention_count"] > baseline.term["mention_count"]
    assert duplicated.term["independent_source_count"] == baseline.term[
        "independent_source_count"
    ]
    assert duplicated.features.independent_corroboration == (
        baseline.features.independent_corroboration
    )
    assert duplicated.semantic_edge.transition_weight == (
        baseline.semantic_edge.transition_weight
    )
    assert duplicated.decision["decision_status"] == baseline.decision[
        "decision_status"
    ]
    assert duplicated.features.authority_and_commitment == (
        baseline.features.authority_and_commitment
    )
    assert duplicated.ranking["scores"] == baseline.ranking["scores"]


def test_reviewed_orchestration_publishes_final_graph_and_inherited_history(
    ranking_fixture,
) -> None:
    reviewed = ranking_fixture.finalize_reviewed_analysis()
    assert reviewed.rankings
    assert all(item["ranking_phase"] == "final" for item in reviewed.rankings)
    assert all(item["semantic_projection_digest"] is not None for item in reviewed.rankings)
    corrected = next(
        item for item in reviewed.rankings
        if item["decision_id"] == ranking_fixture.reviewed_successor_id
    )
    assert corrected["features"]["persistence_across_snapshots"] == (
        ranking_fixture.base_history.persistence_across_snapshots
    )
    assert corrected["features"]["churn"] == ranking_fixture.base_history.churn
```

Run:

```bash
uv run pytest tests/test_ranking.py -q
```

Expected: FAIL because structural ranking APIs do not exist.

- [ ] **Step 2: Implement exact deterministic graph metrics**

Build ephemeral `networkx.DiGraph` from ranking nodes/edges only; sum parallel transition strength and use distance `1/strength` for betweenness. PageRank uses strength, alpha 0.85, tolerance 1e-10, max iterations 100, and equal mass on personalization IDs or uniform when empty.

Confidence-weighted degree ignores direction and sums, for each distinct adjacent canonical node, the maximum transition strength across connecting edges. At no more than 5,000 nodes use exact normalized betweenness. Above 5,000 use `betweenness_centrality_subset` with the first 256 SHA-256-sorted IDs as source and target sample. Unit-test approximation with an injected low threshold on a small graph. Min-max normalize PageRank and degree; constant maps to zero. Clamp betweenness, then structural leverage is 0.60 PageRank + 0.25 bridge + 0.15 degree.

- [ ] **Step 3: Replace provisional rankings with final records**

For each decision, add history persistence/churn. Compute seven-term criticality, six-term review priority, and unchanged confidence from exact resource weights. Round before sorting. Rank each score descending with stable-ID tie-break. Preserve retrieval. Every feature explanation stores value, input IDs, and derivation IDs. Final ranking stage returns and persists one scoring derivation; every ranking cites it. Ranking content includes projection digest and history; identity remains decision/lens/layer/scoring-version.

Replace the Task 11 intrinsic-only tail with one `_finalize_analysis_tail` used by both `analyze_corpus` and `analyze_reviewed_catalog`. It receives an already materialized `Mapping[str, HistoryFeatures]`, builds evidence/semantic graphs, inserts structural metrics, writes final rankings for all three lifecycle lenses, and only then renders the report from the exact current/review selection map defined in Task 11. It never opens snapshots, loads history, infers lineage, or finalizes decision successors. No public finalizer may publish an intrinsic ranking after this task.

`index_repository` resolves the chosen analysis parent and calls `load_decision_history(project, analysis_parent_id, current_source_revision_digest)` before analysis; that verified read needs no current decision. `analyze_corpus` passes the exact immutable `IngestedCorpus` and only `project_config.aliases` to entity resolution, builds the provisional post-reducer catalog, calls `apply_decision_history(history, provisional_catalog, configuration_digest=..., pipeline_digest=...)` exactly once, replaces each current decision with `history_result.updated_decisions_by_id.get(id, decision)`, merges returned lineage/derivations once, and rebuilds the catalog with exactly one content version per stable ID. It passes the resulting per-decision history-feature map into `_finalize_analysis_tail`. `analyze_reviewed_catalog` instead follows each reviewed successor's exact predecessor/lineage back to the base deterministic decision, calls `inherit_history_features`, and passes that map to the same tail before recomputing reviewed semantic projection, structural metrics, scores, and report from the cascaded catalog. Missing/ambiguous inheritance remains explicit unknown input, never a new source revision. For the snapshot's provenance layer, the shared tail builds current, review, and historical projections; the historical projection represents that immutable snapshot's state. It computes and persists `ranking_phase: final` rankings with non-null projection digests for all three lenses, persists the projection-independent evidence graph and lineage, and renders the final report using current lens for sections one/two and review lens for sections three/four. Semantic aggregates remain ephemeral. A query for an unavailable provenance layer returns a selector error and never substitutes another layer or lens. Identical material input still takes observation-only reuse; changed material reruns all global stages, while a same-source-revision rebuild inherits history instead of advancing it.

Extend `tests/test_analysis_pipeline.py` with a repository configuration declaring `Checkout API: checkout-service`; assert the full production orchestrator resolves that alias, and that removing the alias changes the configuration/material digest and leaves the surface unresolved. This proves aliases are not a fixture-only injection path.

- [ ] **Step 4: Run graph/ranking checkpoint**

```bash
uv run pytest tests/test_semantic_graph.py tests/test_history.py tests/test_ranking.py tests/test_analysis_pipeline.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all tests pass; final snapshots contain graph-backed scores with stable ties and reachable derivations.

- [ ] **Step 5: Commit final rankings**

```bash
git add scripts/architecture_graph/ranking.py scripts/architecture_graph/analysis.py scripts/architecture_graph/indexer.py tests/helpers/ranking_graphs.py tests/test_ranking.py tests/test_analysis_pipeline.py
git commit -m "feat: rank decisions with semantic graph metrics"
```

### Task 15: Stable Paging and Bounded Decision Queries

**Files:**
- Create: `scripts/architecture_graph/paging.py`
- Create: `scripts/architecture_graph/decision_queries.py`
- Modify: `scripts/architecture_graph/cli.py`
- Create: `tests/helpers/query_snapshot.py`
- Create: `tests/test_decision_queries.py`

**Interfaces:**
- Produces: `QueryLimits(records=20, depth=2, evidence_excerpts=3, max_chars=12000)`.
- Produces: `QueryPage(snapshot_id, items, truncated, omitted_count, cursor, max_chars, output_format)`; the budget and format are copied from the validated request and are part of cursor binding.
- Produces request dataclasses `DecisionQuery`, `NeighborQuery`, `EvidenceQuery`, `ExplainQuery`, and `ReportQuery`, each carrying `fields: tuple[str, ...] | None` and `output_format`.
- Produces: `query_decisions`, `query_neighbors`, `query_evidence`, `explain_decision`, and `query_report`.
- Produces: `minimum_query_chars(request) -> int` and `render_query_page(page) -> str`; fitting is complete before rendering and the page cannot be rerendered into another format.

- [ ] **Step 1: Write failing order, budget, cursor, and read-only tests**

Create `tests/test_decision_queries.py` against a real published fixture snapshot:

```python
from architecture_graph.canonical import canonical_bytes
from architecture_graph.features import ScoringConfig


def test_decisions_use_stored_rank_and_stable_id() -> None:
    reader = query_reader()
    page = query_decisions(reader, DecisionQuery.defaults(score="criticality"))
    assert [item["decision_id"] for item in page.items] == ["decision:a", "decision:b"]
    assert page.max_chars == 12_000
    assert page.output_format == "json"
    assert len(render_query_page(page)) <= 12_000


def test_cursor_resumes_and_is_bound_to_snapshot_and_query() -> None:
    reader = query_reader()
    first = query_decisions(
        reader, DecisionQuery.defaults(score="criticality", records=1)
    )
    assert first.truncated is True
    assert first.omitted_count == 1
    resumed = query_decisions(
        reader,
        DecisionQuery.defaults(
            score="criticality", records=1, cursor=first.cursor
        ),
    )
    assert [item["decision_id"] for item in resumed.items] == ["decision:b"]
    with pytest.raises(ValueError, match="cursor does not match snapshot or query"):
        query_decisions(
            other_query_reader(),
            DecisionQuery.defaults(score="criticality", records=1, cursor=first.cursor),
        )


def test_neighbors_and_evidence_have_fixed_orders() -> None:
    reader = query_reader()
    neighbors = query_neighbors(reader, NeighborQuery.defaults("entity:checkout", depth=2))
    assert [(item["depth"], -item["edge_weight"], item["edge_type"], item["source_id"], item["target_id"], item["id"]) for item in neighbors.items] == sorted(
        (item["depth"], -item["edge_weight"], item["edge_type"], item["source_id"], item["target_id"], item["id"])
        for item in neighbors.items
    )
    evidence = query_evidence(reader, EvidenceQuery.defaults("decision:a"))
    precedence = {
        authority: index
        for index, authority in enumerate(
            ScoringConfig.load_v1().source_authority_precedence
        )
    }
    order = [
        (
            -precedence[item["source_authority"]],
            item["relative_path"],
            canonical_bytes(item["span"]),
            item["id"],
        )
        for item in evidence.items
    ]
    assert order == sorted(order)


def test_missing_snapshot_query_does_not_mutate_memory(tmp_path) -> None:
    repository, memory = empty_query_project(tmp_path)
    before = sorted(path.relative_to(memory) for path in memory.rglob("*"))
    assert cli_main(["decisions", str(repository), "--memory-root", str(memory), "--json"]) == 2
    assert sorted(path.relative_to(memory) for path in memory.rglob("*")) == before


def test_minimum_budget_still_fits_a_cursor_bound_page() -> None:
    reader = query_reader()
    request = DecisionQuery.defaults(score="criticality", records=1)
    minimum = minimum_query_chars(request)
    page = query_decisions(
        reader, replace(request, limits=replace(request.limits, max_chars=minimum))
    )
    assert page.truncated is True
    assert page.cursor is not None
    assert len(render_query_page(page)) <= minimum


def test_selected_fields_project_before_fitting_and_bind_the_cursor() -> None:
    reader = query_reader()
    request = DecisionQuery.defaults(
        score="criticality",
        records=1,
        fields=("decision_id", "summary"),
    )
    page = query_decisions(reader, request)
    assert set(page.items[0]) == {"decision_id", "summary"}
    with pytest.raises(ValueError, match="cursor does not match snapshot or query"):
        query_decisions(
            reader,
            DecisionQuery.defaults(
                score="criticality",
                records=1,
                fields=("decision_id", "scores"),
                cursor=page.cursor,
            ),
        )
```

Also test: optional evidence/explanation is removed before a complete item; emitted JSON parses and never exceeds `max_chars`; explain priority is summary, scores, graph reasons, evidence, question; invalid IDs/limits/cursors return exit 2.

Run:

```bash
uv run pytest tests/test_decision_queries.py -q
```

Expected: FAIL because paging and decision queries do not exist.

- [ ] **Step 2: Implement canonical cursor binding and complete-item fitting**

Validate nonnegative records/depth/evidence and validate selected fields against the command's output schema. Build the mandatory empty envelope and worst-case bound cursor first; `minimum_query_chars` is the greater of 1,024 and that exact serialized length in the requested output format. Reject smaller budgets. Encode URL-safe base64 canonical JSON containing schema version, resolved snapshot ID, command, normalized arguments/filters, canonical selected-field list, configuration digest, output format, and last emitted sort tuple, plus a SHA-256 of that payload. It is an integrity check, not a security token.

Project each item to the selected fields before fitting while retaining the command's identity field (`decision_id`, edge `id`, or evidence `id`). Fit the entire serialized envelope, including snapshot metadata, omission counts, cursor, and delimiters, inside the query function so its cursor describes the emitted page. Remove optional evidence excerpts, then verbose explanation, then the lowest-priority whole item. If one item cannot fit, emit complete ID/summary/omitted-fields form. Never slice serialized JSON or Markdown. Count Python Unicode code points. `render_query_page` reads `page.output_format`, refuses an override, serializes the fitted page, and asserts the declared budget.

- [ ] **Step 3: Implement streaming record selection and CLI commands**

Orders are: decisions/report by stored selected-lens rank then decision ID; neighbors breadth-first depth, descending edge weight, edge type, source, target; evidence descending source authority, relative path, span, evidence ID; explain summary, features, graph reasons, evidence, architect question.

Resolve the requested provenance layer to its concrete immutable snapshot before reading or cursor validation. Read only needed JSONL files and build temporary maps for that command. Neighbor queries reconstruct only the requested bounded semantic projection from the projection-independent evidence records. Add `report`, `decisions`, `neighbors`, `evidence`, and `explain`. Their repository root is the first positional argument, matching `architecture-graph decisions ROOT`; common options are `--snapshot`, `--lifecycle-lens`, `--provenance-layer`, `--fields`, `--limit`, `--max-chars`, `--cursor`, and `--json`. Neighbors adds `--depth`, evidence adds `--max-evidence`, and decisions adds `--score {criticality,review_priority,confidence}`. `--lens` is not an alias and parser tests reject it, preventing confusion with `--lifecycle-lens`. Known state/query errors print one stderr line and return 2.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_decision_queries.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all tests pass; every response respects record, traversal, evidence, and character limits.

- [ ] **Step 5: Commit bounded decision queries**

```bash
git add scripts/architecture_graph/paging.py scripts/architecture_graph/decision_queries.py scripts/architecture_graph/cli.py tests/helpers/query_snapshot.py tests/test_decision_queries.py
git commit -m "feat: add bounded architecture graph queries"
```

### Task 16: Bounded Deterministic Context Packs

**Files:**
- Create: `scripts/architecture_graph/context.py`
- Modify: `scripts/architecture_graph/cli.py`
- Create: `tests/helpers/context_snapshot.py`
- Create: `tests/test_context.py`

**Interfaces:**
- Produces: `ContextQuery(text, lifecycle_lens, provenance_layer, score, fields, limits, cursor, output_format)`; `fields` is a validated optional tuple of context-item fields.
- Produces: `normalize_context_query`, `build_query_vector`, `sparse_cosine`, `score_context_seed`, `context_edge_weight`, and `query_context`.

- [ ] **Step 1: Write failing seed, traversal, budget, and cursor tests**

Create `tests/test_context.py`:

```python
from dataclasses import replace

import pytest


def test_seed_formula_uses_the_four_approved_weights() -> None:
    ranking = ranking_record(cosine=0.8, identifier_match=1.0, lens_score=0.6, evidence_overlap=0.5)
    score = score_context_seed(("checkout", "events"), ranking)
    assert score.total == 0.8
    assert score.components == {
        "tfidf_cosine": 0.8,
        "identifier_alias_match": 1.0,
        "lens_score": 0.6,
        "evidence_term_overlap": 0.5,
    }


def test_query_cosine_reconstructs_from_jsonl_after_restart(tmp_path) -> None:
    reader = context_reader(
        tmp_path,
        persisted_vector=((2, 0.6), (7, 0.8)),
        include_controlled_predicate_term=True,
    )
    reopened = SnapshotReader.open(reader.project, reader.snapshot_id)
    index = TermIndex.from_snapshot(reopened)
    vector = build_query_vector(
        ("checkout", "events"), index
    )
    assert vector == ((2, 0.6), (7, 0.8))
    assert sparse_cosine(vector, ((2, 0.6), (7, 0.8))) == 1.0
    assert all(
        item["term_kind"] != "controlled_predicate"
        for item in index.by_vocabulary_index.values()
    )


def test_context_selects_eight_seeds_and_decays_without_cycles(tmp_path) -> None:
    reader = context_reader(tmp_path, seed_count=10, include_cycle=True)
    page = query_context(reader, ContextQuery.defaults("payment dependencies", depth=2))
    assert sum(item["selection_kind"] == "seed" for item in page.items) == 8
    selected = {item["id"]: item for item in page.items}
    assert selected["decision:reached-at-depth-one"]["traversal_score"] == 0.32
    assert selected["decision:reached-at-depth-two"]["traversal_score"] == 0.128
    assert all(item["id"].startswith("decision:") for item in page.items)
    assert len({item["id"] for item in page.items}) == len(page.items)
    assert all(
        len(step_ids := [step["next_node_id"] for step in item.get("path", ())])
        == len(set(step_ids))
        for item in page.items
    )


def test_review_and_current_use_different_edge_allowlists(tmp_path) -> None:
    reader = context_reader(tmp_path, include_conflict=True)
    current = query_context(reader, ContextQuery.defaults("checkout", lifecycle_lens="current"))
    review = query_context(reader, ContextQuery.defaults("checkout", lifecycle_lens="review"))
    assert all(item.get("via_edge") != "CONTRADICTS" for item in current.items)
    assert any(item.get("via_edge") == "CONTRADICTS" for item in review.items)
    config = ScoringConfig.load_v1()
    assert context_edge_weight("CONTRADICTS", config) == 1.0
    assert context_edge_weight("SUPERSEDES", config) == 1.0
    assert context_edge_weight("SUPPORTS", config) == 0.70
    assert context_edge_weight("PROPOSES", config) == 0.25
    assert context_edge_weight("REVIEW_OF", config) == 0.25
    historical = query_context(
        reader,
        ContextQuery.defaults("checkout", lifecycle_lens="historical"),
    )
    assert all(item.get("via_edge") != "CONTRADICTS" for item in historical.items)


def test_context_walks_incident_edges_without_persisting_inverses(tmp_path) -> None:
    reader = context_reader(
        tmp_path,
        shared_entity_between_decisions=True,
        incoming_proposal_and_review=True,
    )
    page = query_context(
        reader,
        ContextQuery.defaults("checkout", lifecycle_lens="review", depth=3),
    )
    reached = next(item for item in page.items if item["id"] == "decision:peer")
    assert {step["traversal_direction"] for step in reached["path"]} == {
        "incoming",
        "outgoing",
    }
    seed = next(item for item in page.items if item["selection_kind"] == "seed")
    assert {
        (link["edge_type"], link["traversal_direction"])
        for link in seed["diagnostic_links"]
    } >= {("PROPOSES", "incoming"), ("REVIEW_OF", "incoming")}


def test_context_fields_project_before_fit_and_bind_cursor(tmp_path) -> None:
    reader = context_reader(tmp_path, seed_count=10)
    request = ContextQuery.defaults(
        "checkout",
        records=1,
        fields=("id", "summary"),
    )
    page = query_context(reader, request)
    assert set(page.items[0]) == {"id", "summary"}
    with pytest.raises(ValueError, match="cursor does not match snapshot or query"):
        query_context(
            reader,
            replace(request, fields=("id", "scores"), cursor=page.cursor),
        )


def test_context_is_fitted_before_cursor_and_serialization(tmp_path) -> None:
    reader = context_reader(tmp_path, long_evidence=True)
    page = query_context(reader, ContextQuery.defaults("checkout events", max_chars=2000))
    rendered = render_query_page(page)
    assert len(rendered) <= 2000
    assert __import__("json").loads(rendered)["truncated"] is True
```

Also test stop-term-only rejection and cursor invalidation after normalized query, lens, provenance, scoring digest, output format, or snapshot changes.

Run:

```bash
uv run pytest tests/test_context.py -q
```

Expected: FAIL because deterministic context selection does not exist.

- [ ] **Step 2: Implement exact lexical seed scoring**

Normalize with the snapshot's recorded normalizer resource digest and reject no-token queries. Count normalized query tokens, multiply each in-vocabulary raw count by the exact IDF stored at that term's vocabulary coordinate, then L2-normalize the nonzero sparse query vector; out-of-vocabulary tokens contribute no coordinate. Compute cosine as the two-pointer dot product of the query pairs and the persisted L2-normalized decision pairs, with zero for an empty vector. No corpus refit occurs at query time. Identifier/alias match is 1.00 exact, 0.70 token-boundary prefix, zero otherwise. Evidence overlap is fraction of distinct normalized query tokens in bounded evidence terms. Lens feature selects stored criticality/review priority/confidence.

```python
total = (
    0.55 * tfidf_cosine
    + 0.25 * identifier_alias_match
    + 0.10 * lens_score
    + 0.10 * evidence_term_overlap
)
```

Sort descending total then decision ID and keep at most eight seeds.

- [ ] **Step 3: Implement typed traversal and the 10/55/30/5 budget**

Current allows GOVERNS, ADDRESSES, HAS_CONSEQUENCE, AFFECTS, CONSTRAINS, REQUIRES, PROHIBITS, DEPENDS_ON, CALLS, READS_FROM, WRITES_TO, PUBLISHES_TO, SUBSCRIBES_TO. Review additionally allows CONTRADICTS, SUPERSEDES, SUPPORTS, PROPOSES, and REVIEW_OF. Historical uses the current semantic-type allowlist over all eligible records captured in the selected immutable snapshot; V1 has no `as_of` input. Current/historical semantic edges use `edge_base_weights`; review-only edges use the separate `context_traversal_weights` table: CONTRADICTS and SUPERSEDES 1.00, SUPPORTS 0.70, and PROPOSES/REVIEW_OF 0.25. `context_edge_weight` rejects a review-only edge missing from that table. These context weights never enter PageRank, degree, or betweenness. Never traverse evidence, derivation, containment, or alias-candidate edges.

Traverse every allowed semantic edge as an incident edge in either direction without synthesizing or persisting an inverse. Preserve the canonical stored `from_id`/`to_id` orientation, and add `traversal_direction: outgoing|incoming` plus the actual `next_node_id` to each path step relative to the node being expanded. This allows `decision -> shared entity <- decision` discovery while leaving directed ranking semantics unchanged. In the review lens, incoming `PROPOSES` and `REVIEW_OF` edges attached to a selected or reached decision are returned as bounded `diagnostic_links`; proposal/review nodes are not enqueued as routes to another decision.

Traversal priority is seed score × path edge weights × `0.5 ** depth`. Each queued path carries a path-local visited node-ID and edge-ID set; never extend it through a previously visited node or edge. Keep the highest value/path per internal node, then deduplicate final decisions to their single best score/path. Traversed entity/term nodes only discover connected decisions and never appear as output items. Sort output decisions by traversal score, selected lens score, stable ID. Validate `fields` against the context-item schema, always retain `id`, and project before fitting. First reserve the exact mandatory page metadata/cursor envelope. Divide only the remaining budget in the relative weights 55:30:5 for decision summaries/explanations, evidence, and omissions, using integer floors and returning rounding remainder to summaries; the configured 10% metadata share is a target, but mandatory metadata may exceed it and is never truncated. Clip evidence on sentence/source-line boundary. Fit before cursor creation. Context cursor additionally binds normalized query, lens, provenance, canonical selected fields, scoring digests, and output format. Return only ranked decisions, score explanations, origin labels, short evidence, diagnostic links, and architect questions.

Add `architecture-graph context ROOT QUERY` with selector, `--fields`, limit, depth, max-character, cursor, and output options.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_context.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all tests pass; context never emits a complete snapshot or violates its character budget.

- [ ] **Step 5: Commit context packs**

```bash
git add scripts/architecture_graph/context.py scripts/architecture_graph/cli.py tests/helpers/context_snapshot.py tests/test_context.py
git commit -m "feat: build bounded architecture context packs"
```

### Task 17: Bounded Semantic Snapshot Diff

**Files:**
- Create: `scripts/architecture_graph/diff.py`
- Modify: `scripts/architecture_graph/cli.py`
- Create: `tests/helpers/diff_snapshots.py`
- Create: `tests/test_diff.py`

**Interfaces:**
- Produces: `DiffItem` and `SnapshotDiff(items, truncated, omitted_count, cursor, max_chars, output_format, fields)`.
- Produces: `diff_snapshots(left, right, limits, output_format, cursor=None, fields=None) -> SnapshotDiff`; selected fields are validated and canonicalized before fitting.
- Produces: `render_snapshot_diff(value) -> str`; fitting is already complete and format-bound.

- [ ] **Step 1: Write failing semantic-change, explanation, cursor, and budget tests**

Create `tests/test_diff.py`:

```python
import pytest


def test_diff_reports_architecture_changes_not_recursive_json_noise(tmp_path) -> None:
    left, right = checkout_readers(tmp_path)
    result = diff_snapshots(left, right, QueryLimits(), "json")
    keys = {(item.category, item.change, item.stable_id) for item in result.items}
    assert ("claim", "modified", "claim:event-publication") in keys
    assert ("decision_status", "modified", "decision:adr-002:database") in keys
    assert ("conflict", "added", "edge:production-database-conflict") in keys
    assert ("overspecification", "resolved", "decision:adr-002:database") in keys
    assert ("ranking", "moved", "decision:adr-001:events") in keys


def test_rank_movement_has_feature_deltas(tmp_path) -> None:
    result = diff_snapshots(*checkout_readers(tmp_path), QueryLimits(), "json")
    movement = next(item for item in result.items if item.category == "ranking")
    criticality = movement.after["by_projection"]["current"]["deterministic"][
        "criticality"
    ]
    assert criticality["rank_delta"] == -2
    assert criticality["feature_deltas"]["cross_cutting_scope"] == 0.15
    assert movement.input_ids == tuple(sorted(movement.input_ids))


def test_multi_lens_ranking_diff_is_one_cursor_safe_item_per_decision(tmp_path) -> None:
    left, right = checkout_readers(tmp_path, rank_changes_in_all_lenses=True)
    first = diff_snapshots(left, right, QueryLimits(records=1), "json")
    second = diff_snapshots(
        left,
        right,
        QueryLimits(records=1),
        "json",
        first.cursor,
    )
    ranking_items = [
        item for item in (*first.items, *second.items)
        if item.category == "ranking"
    ]
    assert len({item.stable_id for item in ranking_items}) == len(ranking_items)
    assert all(
        set(item.after["by_projection"]) == {"current", "review", "historical"}
        for item in ranking_items
    )


def test_diff_cursor_binds_both_snapshots_query_and_output(tmp_path) -> None:
    left, right = checkout_readers(tmp_path)
    first = diff_snapshots(left, right, QueryLimits(records=1), "json")
    assert first.truncated is True and first.cursor is not None
    with pytest.raises(ValueError, match="cursor does not match snapshot or query"):
        diff_snapshots(right, left, QueryLimits(records=1), "json", first.cursor)
    assert first.output_format == "json"
    assert len(render_snapshot_diff(first)) <= 12_000


def test_diff_fields_project_before_fit_and_bind_cursor(tmp_path) -> None:
    left, right = checkout_readers(tmp_path)
    fields = ("category", "change", "stable_id")
    first = diff_snapshots(
        left,
        right,
        QueryLimits(records=1),
        "json",
        fields=fields,
    )
    assert set(first.items[0].as_json()) == set(fields)
    with pytest.raises(ValueError, match="cursor does not match snapshot or query"):
        diff_snapshots(
            left,
            right,
            QueryLimits(records=1),
            "json",
            first.cursor,
            fields=("category", "change", "stable_id", "after"),
        )


def test_changed_decision_identity_is_paired_through_right_lineage(tmp_path) -> None:
    left, right = checkout_readers(tmp_path, decision_identity_change=True)
    result = diff_snapshots(left, right, QueryLimits(), "json")
    transition = next(
        item for item in result.items
        if item.category == "decision_status"
        and item.stable_id == "decision:new-id"
    )
    assert transition.before["id"] == "decision:old-id"
    assert transition.after["id"] == "decision:new-id"
    assert any(
        item.category == "ranking" and item.stable_id == "decision:new-id"
        for item in result.items
    )


def test_non_adjacent_diff_follows_changed_identity_chain(tmp_path) -> None:
    v1, _, v3 = checkout_three_revision_readers(
        tmp_path,
        decision_identity_change_at_v2=True,
    )
    result = diff_snapshots(v1, v3, QueryLimits(), "json")
    transition = next(
        item for item in result.items
        if item.category == "decision_status"
        and item.stable_id == "decision:v2-successor"
    )
    assert transition.before["id"] == "decision:v1-predecessor"
    assert any(
        item.category == "ranking"
        and item.stable_id == "decision:v2-successor"
        for item in result.items
    )


def test_non_adjacent_diff_stops_at_the_bound_lineage_depth(tmp_path) -> None:
    v1, _, _, v4 = checkout_four_revision_readers(
        tmp_path,
        decision_identity_change_at_v2=True,
    )
    result = diff_snapshots(v1, v4, QueryLimits(depth=2), "json")
    added = next(
        item for item in result.items
        if item.category == "decision_status"
        and item.change == "added"
        and item.stable_id == "decision:v2-successor"
    )
    assert added.explanation["lineage_pairing"]["status"] == "limit_reached"
    assert added.explanation["lineage_pairing"]["max_hops"] == 2
    assert any(
        item.category == "decision_status"
        and item.change == "removed"
        and item.stable_id == "decision:v1-predecessor"
        for item in result.items
    )
```

Also test term/claim additions/removals/modifications, entity merge/split lineage, new/resolved conflict and over-specification, derivation changes, and source coverage changes.

Run:

```bash
uv run pytest tests/test_diff.py -q
```

Expected: FAIL because semantic snapshot diff does not exist.

- [ ] **Step 2: Implement stable semantic matching and explanations**

Stream required JSONL pairs. Terms/claims use stable identity: left-only removed, right-only added, same ID/different digest modified. Use right lineage for entity merge/split. For decisions, follow each unique, verified right-side predecessor/decision-lineage chain backward through declared snapshot ancestry for at most `limits.depth` predecessor hops, checking exact IDs/content digests at every hop and rejecting cycles or ambiguous branches. Pair endpoints only when that bounded walk reaches the left snapshot. This supports non-adjacent V1→V3 diffs when an identity changed in V2 and the caller's depth permits it. When the walk reaches the depth limit first, do not guess: emit the normal unpaired removal/addition items and attach a `lineage_pairing` explanation with `status: limit_reached`, `max_hops`, and the last verified locator. Ambiguous or invalid lineage gets the corresponding explicit explanation. Pair remaining decisions by stable ID. Compare scalar status, `status_resolution`, distinct candidate status values, CONTRADICTS identities, over-spec result, and rankings across each paired predecessor/successor decision, using the successor ID as the diff stable ID; then report unpaired additions/removals. A decision-status explanation shows both resolution and candidate-value deltas. Also compare derivation identity/content and source parse/warning coverage. Emit at most one ranking `DiffItem` per paired decision. Its deterministic `by_projection[lifecycle_lens][provenance_layer][score]` map aggregates old/new rank, score delta, and feature deltas for every stored lens/layer and each of criticality, review priority, and confidence. Missing sides are explicit nulls. This keeps `(category, change, stable_id)` unique and cursor-safe.

Category order is term, claim, entity_lineage, decision_status, conflict, overspecification, ranking, derivation, source_coverage. Change order is added, modified, moved, resolved, removed, then stable ID. Do not expose generic recursive JSON diff.

Validate selected fields against the diff-item schema and always retain `category`, `change`, and `stable_id`. Project before fitting. Fit the complete format-bound `SnapshotDiff` envelope before cursor, using the same computed minimum budget and mandatory-envelope accounting as `QueryPage`. Cursor binds both snapshots, command, output format, canonical selected fields, normalized limits/filters, and last category/change/ID tuple. `render_snapshot_diff` reads the stored format and refuses an override. Derived explanations name input and derivation IDs.

- [ ] **Step 3: Add read-only CLI dispatch**

Add `architecture-graph diff ROOT SNAPSHOT_A SNAPSHOT_B` with memory root, `--fields`, `--limit`, `--depth`, `--max-chars`, cursor, and JSON/Markdown. `--depth` populates the same validated, cursor-bound `QueryLimits.depth` used by lineage pairing. Unknown snapshots, invalid fields/limits, and stale cursors return 2 without changing memory.

- [ ] **Step 4: Run focused and cumulative tests**

```bash
uv run pytest tests/test_diff.py -q
uv run pytest -q
uv run python -m compileall -q scripts
```

Expected: all tests pass; diff is bounded and architecture-semantic.

- [ ] **Step 5: Commit semantic diff**

```bash
git add scripts/architecture_graph/diff.py scripts/architecture_graph/cli.py tests/helpers/diff_snapshots.py tests/test_diff.py
git commit -m "feat: diff architecture decisions across snapshots"
```

### Task 18: Deterministic Completion Golden and Skill Handoff

**Files:**
- Create: `tests/fixtures/corpora/checkout-v1/.architecture-graph.yaml`
- Create: `tests/fixtures/corpora/checkout-v1/docs/adrs/ADR-001-order-events.md`
- Create: `tests/fixtures/corpora/checkout-v1/docs/adrs/ADR-002-postgresql.md`
- Create: `tests/fixtures/corpora/checkout-v1/docs/architecture/topology.md`
- Create: `tests/fixtures/corpora/checkout-v2/.architecture-graph.yaml`
- Create: `tests/fixtures/corpora/checkout-v2/docs/adrs/ADR-001-order-events.md`
- Create: `tests/fixtures/corpora/checkout-v2/docs/adrs/ADR-002-postgresql.md`
- Create: `tests/fixtures/corpora/checkout-v2/docs/adrs/ADR-003-event-retention.md`
- Create: `tests/fixtures/corpora/checkout-v2/docs/architecture/topology.md`
- Create: `tests/fixtures/golden/checkout-v1/manifest.json`
- Create: fourteen JSONL payloads and `report.md` under `tests/fixtures/golden/checkout-v1/`
- Create: `tests/update_phase2_goldens.py`
- Create: `tests/test_phase2_golden.py`
- Modify: `SKILL.md`
- Modify: `references/agent-usage.md`
- Modify: `references/configuration.md`

**Interfaces:**
- Locks byte-level deterministic snapshot, score explanation, report, bounded-query, and semantic-diff contracts.
- Documents the JSON/JSONL-only status-first workflow; no README or database is added.

- [ ] **Step 1: Add adversarial V1 and V2 corpora**

V1 contains accepted must-level OrderPlaced publication with driver, production scope, consequence; proposed PostgreSQL/version prescription missing driver/consequence; passive, conditional, must-not prose; repeated system/service/data boilerplate; Mermaid-only topology; conflicting environment scope; old superseded statement. V2 changes database status/scope, adds retention, resolves one conflict, and adds cross-cutting evidence sufficient to move a rank. Every expected claim has exact source evidence. Every selected Markdown source, including `topology.md`, has a unique explicit front-matter document ID that remains stable between V1 and V2. The portable golden is forbidden from exercising the checkout-root-dependent fallback logical-source ID; fallback portability is tested separately with the same project identity.

Both portable golden corpora check in this exact `.architecture-graph.yaml`, with identical bytes in V1 and V2:

```yaml
schema_version: 1
include:
  - docs/adrs/*.md
  - docs/adrs/**/*.md
  - docs/architecture/*.md
  - docs/architecture/**/*.md
source_roles:
  "docs/adrs/*.md": adr
  "docs/architecture/*.md": architecture
spacy_model: null
```

The explicit include list is required because the Phase 1 default uses singular `docs/adr/**`. Do not configure a blanket ADR authority: leaving `source_authorities` absent allows each ADR's parsed accepted/proposed front-matter status to select the correct authority, while topology retains the default maintained-architecture treatment. The golden exercises the versioned tokenizer/rule fallback and is byte-identical whether `en_core_web_sm` happens to be installed or not. Keep installed-model, missing-model, and artifact-change behavior in the separate Task 2 integration tests; never make a portable byte golden depend on optional local packages.

- [ ] **Step 2: Add deterministic golden updater and failing acceptance tests**

`tests/update_phase2_goldens.py` copies checkout-v1, including its explicit `spacy_model: null` configuration, to a temporary Git repo, creates one fixed fixture commit, indexes at `2026-07-19T10:00:00Z`, and copies only manifest, all `RECORD_TYPES` JSONL files, and report to the golden directory in sorted order. The updater asserts the loaded configuration has a null model, all expected ADR paths are selected, and the running interpreter is exactly CPython 3.12.13 before indexing. `tests/test_phase2_golden.py` makes the same interpreter assertion. The project-level `.python-version` and `uv run` therefore bind the environment-sensitive pipeline preimage instead of pretending snapshots from different Python patches are byte-identical.

`tests/test_phase2_golden.py` asserts:

```python
first = index_fixture(checkout_v1, memory_a, "2026-07-19T10:00:00Z")
second = index_fixture(checkout_v1, memory_b, "2026-07-19T11:00:00Z")
assert first.snapshot_id == second.snapshot_id
assert canonical_payload(memory_a, first.snapshot_id) == canonical_payload(
    memory_b, second.snapshot_id
)
assert canonical_payload(memory_a, first.snapshot_id) == checked_in_golden(
    "checkout-v1"
)
```

It also copies the fixture twice beneath different temporary checkout roots, initializes each with the same fixed relative corpus and commit metadata, indexes them into separate memory roots, and compares the complete canonical payload byte-for-byte:

```python
def test_golden_is_checkout_root_portable(tmp_path: Path) -> None:
    left = copy_fixture_to(tmp_path / "left")
    right = copy_fixture_to(tmp_path / "right")
    assert every_selected_markdown_has_unique_explicit_document_id(left)
    assert every_selected_markdown_has_unique_explicit_document_id(right)
    assert canonical_payload_files(index_portable(left)) == canonical_payload_files(
        index_portable(right)
    )
```

`canonical_payload_files` compares manifest, all fourteen JSONL payloads, and `report.md`; it excludes only observations and current-pointer files. The helper fails if a selected Markdown fixture would use a fallback logical-source ID.

Block `socket.socket` and assert indexing succeeds. Observation IDs/times differ outside snapshots. Every report assertion resolves claim/evidence; every score/diagnostic resolves inputs/derivations. No file ends `.db`, `.sqlite`, or `.sqlite3`. Parsing CLI `enrich` raises `SystemExit` because no live enrichment command exists. V1→V2 changes affected term/entity/claim/decision/edge/ranking/derivation/warning/report payloads and semantic diff reports claim, decision, conflict, rank, derivation, and coverage changes, proving corpus-global recomputation.

- [ ] **Step 3: Verify red, generate, inspect, and verify green**

```bash
uv run pytest tests/test_phase2_golden.py -q
```

Expected: FAIL because the checked-in golden payload is absent.

Run:

```bash
uv run python tests/update_phase2_goldens.py
git diff -- tests/fixtures/golden/checkout-v1
uv run pytest tests/test_phase2_golden.py -q
```

Expected: updater writes one manifest, fourteen JSONL files, and one report; inspection shows evidence spans, producer labels, decision ranks, feature explanations, and report citations matching the fixture; focused tests pass.

- [ ] **Step 4: Finalize progressive skill guidance**

Update `SKILL.md` workflow to status, index when stale, use bounded decisions/context/explain/evidence/diff, append an exact human review when requested, and finalize a reviewed snapshot explicitly. State that deterministic, LLM, and human provenance are independently selectable and possible over-specification is a question queue, not a correctness verdict.

Add exact examples to `references/agent-usage.md`:

```bash
architecture-graph decisions . --score criticality --limit 10 --json
architecture-graph context . "payment dependencies" --max-chars 12000 --json
architecture-graph explain . decision:adr-001:events --json
architecture-graph evidence . decision:adr-001:events --max-evidence 3 --json
architecture-graph diff . deterministic:LEFT deterministic:RIGHT --limit 20 --json
architecture-graph review append . --target-kind claim --target-id claim:ID --target-content-digest sha256:DIGEST --verdict verify --reviewer-id architect@example.com --json
architecture-graph review finalize . --json
```

Update configuration guidance: `spacy_model` names an already-installed package; status and index use the same package-root-confined, regular-file-only, no-symlink artifact traversal capped at 8,192 visited paths, 4,096 files, and 536,870,912 bytes; an unsafe or over-limit package fails visibly rather than producing a partial fingerprint. Indexing records observed package/model versions and artifact digest; absence emits `model_unavailable`; no command downloads it.

- [ ] **Step 5: Run complete verification**

```bash
uv lock --check
uv run pytest -q
uv run python -m compileall -q scripts
uv run python /Users/patrick/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
uv run architecture-graph --help
uv run architecture-graph decisions --help
uv run architecture-graph context --help
uv run architecture-graph diff --help
uv run architecture-graph review append --help
uv run architecture-graph review finalize --help
bin/architecture-graph --version
git diff --check
```

Expected: lock check, suite, compileall, help, wrapper, and diff check pass; skill validation prints `Skill is valid!`; no network, LLM, model download, database, or unbounded snapshot query occurs.

- [ ] **Step 6: Commit deterministic completion**

```bash
git add SKILL.md references/agent-usage.md references/configuration.md tests/fixtures/corpora tests/fixtures/golden tests/update_phase2_goldens.py tests/test_phase2_golden.py
git commit -m "test: lock deterministic architecture analysis output"
```

Phase 2 is complete when the full matrix passes from a clean checkout whose uv environment was synchronized in advance. Phase 3 LLM proposal generation remains a separate plan and cannot be inferred from this checkpoint.
