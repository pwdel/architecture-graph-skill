# Architecture Graph v0.4.0 Architecture

Architecture Graph converts selected architecture sources into immutable,
evidence-backed memory. Engineers and external agents can query that memory
without loading the full source corpus into a context window. The
[interactive diagram](../architecture.html) presents the pipeline as five
clickable flows. The shorter [diagram companion](../architecture.md) records
the same component and handoff model.

## Purpose and scope

Version 0.4.0 reads architecture records from Markdown, plain text, JSON,
YAML, Mermaid, and PlantUML. It preserves source locations, derives semantic
records, constructs a typed evidence graph, calculates independent rankings,
and publishes the result as an immutable JSONL snapshot. Query commands return
bounded projections from that complete snapshot. An optional rationale overlay
can resolve decision-local rationale without changing the base graph or its
scores.

The system supports evidence-backed navigation and review. It does not replace
an architect's judgment, approve a proposal, or make an unaccepted decision
current.

## Provenance boundary

Architecture Graph v0.4.0 does not call an LLM internally. Ingestion,
tokenization, TF-IDF, controlled SVO extraction, entity resolution, decision
reduction, graph construction, PageRank, scoring, rationale resolution,
validation, bounded retrieval, and built-in report composition are
**Deterministic**.

An agent may perform **Optional external LLM** interpretation after the tool
returns a bounded query result or cited report. That interpretation runs
outside architecture-graph. It cannot enter the immutable base snapshot or
the rationale overlay.

A person supplies **Human/control** input by invoking commands, authorizing
writes, and reviewing conclusions. Authorization and engineering review are
governance controls rather than algorithms.

## Components and responsibilities

| Component | Responsibility | Writes memory | Provenance |
| --- | --- | --- | --- |
| Agent or engineer | Selects commands, corpora, bounds, and authorized mutations; interprets results | Only through explicit write commands | Human/control; Optional external LLM after delivery |
| CLI and capability gate | Parses commands, selects corpora and snapshots, enforces capabilities and output bounds | Dispatches authorized writes | Deterministic |
| Corpus and configuration | Discovers supported inputs and verifies memory placement | No snapshot records | Deterministic |
| Format ingestion | Produces source, segment, evidence, derivation, and warning records with source spans | No | Deterministic |
| Semantic analysis | Produces terms, entities, qualified SVO claims, decision candidates, and decisions | No | Deterministic |
| Typed graph and scoring | Constructs typed edges, runs PageRank, and calculates `scoring-v1` dimensions | No | Deterministic |
| Snapshot storage | Validates and atomically publishes content-addressed JSONL records and manifests | Base snapshots | Deterministic |
| Rationale resolver | Classifies decision-local rationale and validates its provenance | Separate overlays only | Deterministic |
| Query and report layer | Projects bounded records and composes cited base-plus-overlay reports | No | Deterministic |

## End-to-end indexing pipeline

`architecture-graph index PATH --json` performs one integrated operation:

1. The CLI validates the command, input selection, memory location, and write
   conditions.
2. Format adapters segment supported files and retain source versions, paths,
   structural context, and spans.
3. Rule Tokenization normalizes evidence and extracts tokens, noun phrases,
   and acronyms.
4. Sparse TF-IDF Term Discovery ranks terms across the complete selected
   corpus.
5. Controlled SVO Relation Extraction, Exact-Key Entity Resolution, and relation
   qualification create typed claims with modality, polarity, scope, and
   applicability.
6. Decision Candidate Extraction and Decision Reduction produce normalized
   decision records and diagnostics.
7. Typed Evidence Graph Construction connects source evidence, semantic
   records, claims, and decisions.
8. PageRank and Independent Dimension Scoring calculate the frozen ranking
   records.
9. Snapshot validation checks record schemas and references. Canonical
   Content-Addressed Publication then writes one immutable base snapshot.

Graph construction is part of indexing. The diagram's **Build graph** flow is
a focused view of steps 3 through 8, not a second command or persisted pass.
The base snapshot contains semantic, graph, and ranking records together.
There is no preliminary ranking snapshot followed by a separate graph
snapshot.

## Algorithm registry

Existing resource names, derivation names, schema versions, and scoring rule
versions are stable implementation identifiers. A descriptive implementation
label explains an otherwise unnamed mechanism without creating a new
compatibility contract.

| Pipeline stage | Algorithm or mechanism | Identifier or fixed parameters | Naming status | Provenance |
| --- | --- | --- | --- | --- |
| Text parsing | Rule Tokenization | `rule_tokenizer` | Existing derivation name | Deterministic |
| Term extraction | Sparse TF-IDF Term Discovery | `sparse_tfidf`, `terms-en-v1` | Existing derivation and resource identifiers | Deterministic |
| SVO extraction | Controlled SVO Relation Extraction | `predicates-v1` plus fixed code rules | Descriptive label over an existing rule resource | Deterministic |
| Entity resolution | Exact-Key Entity Resolution | `exact_entity_key` | Existing derivation name | Deterministic |
| Modality and status | Relation Qualification | Fixed qualifier rules | Descriptive implementation label | Deterministic |
| Decision discovery | Decision Candidate Extraction | `decision-rules-v1` | Descriptive label over an existing resource | Deterministic |
| Decision normalization | Decision Reduction | `decision_reducer` | Existing derivation name | Deterministic |
| Graph construction | Typed Evidence Graph Construction | Six typed edge families | Descriptive implementation label | Deterministic |
| Graph centrality | PageRank | Damping factor of `0.85`; 24 iterations | Standard named algorithm with fixed parameters | Deterministic |
| Architecture scoring | Independent Dimension Scoring | `scoring-v1` | Existing frozen rule identifier | Deterministic |
| Rationale detection | Decision-Local Rationale Resolution | `rationale-rules-v1` | Descriptive label over an existing rule identifier | Deterministic |
| Overlay validation | Rationale Overlay Contract Validation | Overlay schema `1` | Descriptive label over an existing schema contract | Deterministic |
| Persistence | Canonical Content-Addressed Publication | Canonical JSON and content digest | Descriptive implementation label | Deterministic |
| Retrieval | Stable Bounded Projection | Cursor binding, fields, `limit`, and `max_chars` | Descriptive implementation label | Deterministic |
| Report production | Cited Report Composition | Built-in report rules | Descriptive implementation label | Deterministic |

Sparse TF-IDF uses logarithmically scaled term frequency and inverse document
frequency. It considers individual tokens and noun phrases, and records
glossary and acronym discovery signals. Controlled SVO Relation Extraction
matches canonical predicate surfaces in prose or text-native diagram edges.
It does not use a generative or statistical language model.

The frozen pipeline advertises `extraction-rules-en-v1` and
`entity-rules-v1` as versioned resources. The current relation extractor and
entity resolver do not load those resources directly: relation extraction
loads `predicates-v1`, while entity resolution canonicalizes exact case-folded
keys and records the `exact_entity_key` derivation. The distinction prevents a
declared capability from being mistaken for an active algorithm input.

## Typed graph and independent scoring

Typed Evidence Graph Construction creates these edge families:

- `CONTAINS` links sources to segments and segments to evidence.
- `MENTIONS` links evidence to terms and entities.
- `ASSERTS` links evidence to claims.
- `SUBJECT_OF` and `OBJECT_OF` connect entities to qualified SVO claims.
- `SUPPORTS` connects claims to reduced decisions.

PageRank runs on the complete typed graph with a damping factor of `0.85` and
24 iterations. The implementation sorts nodes and edges and normalizes scores
against the maximum result, which keeps fixed inputs reproducible.

Independent Dimension Scoring stores six separate `scoring-v1` dimensions:

| Dimension | Principal features |
| --- | --- |
| Navigation | Typed degree, PageRank, TF-IDF lexical salience, evidence breadth |
| Criticality | Required modality and evidence breadth |
| Review priority | Missing rationale and contradiction signals |
| Extraction confidence | SVO tuple completeness and structural explicitness |
| Corroboration | Distinct supporting source-content hashes |
| Completeness | Decision title, statement, status, rationale, consequences, and scope |

The system does not collapse these dimensions into a response-dependent
importance score. Consumers select the dimension that matches their question.

## Immutable JSONL base snapshots

The indexer validates semantic-schema-2 records and their references before
publication. It serializes canonical JSONL records, calculates content
digests, writes a manifest, and advances the corpus's current pointer only
after all files pass integrity checks. Identical deterministic inputs produce
the same snapshot identity only within the same project, corpus selection, configuration, pipeline, and analysis history. Project identity includes the
absolute project root, and logical source identity can include the parent
snapshot. A published base snapshot never changes.

Source evidence and derivation records remain in the same base, so an engineer
can trace a term, claim, edge, decision, or score back to exact source spans and
the fixed rules that produced it.

## Bounded queries

Commands such as `terms`, `decisions`, `neighbors`, `evidence`, and `explain`
open one validated base snapshot. Stable Bounded Projection applies ordering,
field selection, pagination, graph depth, `limit`, and `max_chars` after the
tool reads the frozen records.

Indexing and ranking cover the complete selected corpus. Response bounds
control only the returned envelope, which protects an engineer's or external
agent's context window without changing graph or ranking inputs. Stable cursors
bind the snapshot and normalized query arguments so follow-up reads preserve
the same view.

## Rationale overlays

Decision-Local Rationale Resolution reads base decisions, segments, evidence,
diagnostics, and scopes. `rationale-rules-v1` recognizes explicit
`rationale` fields and approved aliases such as `context`, `justification`,
`reason`, and `why_now`. It classifies each decision as `explicit`,
`recognized_alias`, `ambiguous`, or `missing`.

Rationale Overlay Contract Validation requires every resolution to reference
the exact base snapshot, decision digest, eligible decision-local evidence,
and valid derivations. It also requires one resolution per base decision and
rejects any overlay record whose `rank_eligible: false` invariant does not
hold.

The validated overlay receives its own content-addressed identity and current
pointer. It binds to the base snapshot and ranking digest but does not rewrite
base diagnostics. Overlay records never enter TF-IDF, graph construction,
PageRank, or `scoring-v1`.

## Cited report composition

Cited Report Composition opens the immutable base and, when available, one
compatible rationale overlay. The report layer builds bounded decision and
term summaries, retains base citations, reports coverage, and exposes stable
assertion identifiers for retrieving complete evidence ledgers.

The built-in report is deterministic. An engineer may give that report to an
external LLM for synthesis or follow-up exploration. The LLM's response remains
an external interpretation unless a separate human-authorized workflow records
it elsewhere.

## Authorization and engineering review

Read commands do not create or replace memory. `index` and `rationale build`
are explicit write operations. Project-local memory must use an ignored
`.architecture-graph/` directory or an explicitly managed memory root. A caller
must authorize any repository change needed to satisfy that guard.

Engineering review evaluates whether extracted records match the source,
whether proposals have been mistaken for accepted commitments, and whether
the selected score dimension fits the question. Review can reject or qualify
a conclusion, but v0.4.0 does not mutate a human-review ledger.

## Current exclusions

Version 0.4.0 does not implement raster image interpretation, human review
mutation, semantic snapshot diff, or decision lineage. It analyzes prose and
text-native diagrams. These exclusions apply even when an external agent uses
an LLM to interpret a bounded result.
