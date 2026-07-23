# Architecture Graph v0.4.0 Algorithm Provenance Documentation Design

## Objective

Document the v0.4.0 architecture as a standalone engineering reference and
extend the interactive diagram so readers can distinguish deterministic
processing, optional external LLM interpretation, and human governance.

The change adds `README/architecture-v0.4.0.md` and updates the existing root
`architecture.html`. The concise root `architecture.md` remains the companion
to the interactive diagram.

## Provenance model

The documentation uses three provenance categories:

- **Deterministic**: architecture-graph code executes fixed parsing, analysis,
  graph, scoring, validation, storage, query, and report rules.
- **Optional external LLM**: an agent may interpret bounded tool output after
  architecture-graph returns it. The LLM is outside architecture-graph and
  does not create base or overlay records in v0.4.0.
- **Human/control**: a person invokes commands, authorizes writes, and reviews
  engineering conclusions. Authorization and review are governance controls,
  not algorithms.

The diagram and README must state that v0.4.0 does not call an LLM internally.

## Algorithm naming policy

Existing resource names, derivation names, schema versions, and scoring rule
versions are authoritative identifiers. Unversioned mechanisms receive clear
descriptive labels, but the documentation must not present those labels as new
compatibility contracts.

| Pipeline stage | Display name | Existing identifier or parameter | Provenance | Naming status |
| --- | --- | --- | --- | --- |
| Text parsing | Rule Tokenization | `rule_tokenizer` | Deterministic | Existing derivation name |
| Term extraction | Sparse TF-IDF Term Discovery | `sparse_tfidf`, `terms-en-v1` | Deterministic | Existing derivation and resource identifiers |
| SVO extraction | Controlled SVO Relation Extraction | `predicates-v1` plus fixed code rules | Deterministic | Descriptive name over the directly loaded rule resource |
| Entity resolution | Exact-Key Entity Resolution | `exact_entity_key` | Deterministic | Existing derivation name |
| Modality and status | Relation Qualification | Fixed qualifier rules | Deterministic | Descriptive implementation label |
| Decision discovery | Decision Candidate Extraction | `decision-rules-v1` | Deterministic | Descriptive name over an existing resource identifier |
| Decision normalization | Decision Reduction | `decision_reducer` | Deterministic | Existing derivation name |
| Graph construction | Typed Evidence Graph Construction | `CONTAINS`, `MENTIONS`, `ASSERTS`, `SUBJECT_OF`, `OBJECT_OF`, `SUPPORTS` | Deterministic | Descriptive implementation label |
| Graph centrality | PageRank | damping `0.85`, 24 iterations | Deterministic | Standard named algorithm with fixed implementation parameters |
| Architecture scoring | Independent Dimension Scoring | `scoring-v1` | Deterministic | Existing frozen rule identifier |
| Rationale detection | Decision-Local Rationale Resolution | `rationale-rules-v1` | Deterministic | Descriptive name over an existing rule identifier |
| Overlay validation | Rationale Overlay Contract Validation | overlay schema `1` | Deterministic | Descriptive name over an existing schema contract |
| Persistence | Canonical Content-Addressed Publication | canonical JSON and content digest | Deterministic | Descriptive implementation label |
| Retrieval | Stable Bounded Projection | cursor binding, `limit`, fields, and `max_chars` | Deterministic | Descriptive implementation label |
| Report production | Cited Report Composition | built-in report rules | Deterministic | Descriptive implementation label |
| Interpretation | Agent-Assisted Interpretation | external caller | Optional external LLM | Descriptive external activity |
| Authorization | Write Authorization Gate | explicit command/user approval | Human/control | Governance control |
| Review | Engineering Review | human review process | Human/control | Governance activity |

## Interactive diagram changes

The existing topology and five flows remain intact. The update adds:

- a provenance legend for Deterministic, Optional external LLM, and
  Human/control;
- compact provenance badges on relevant nodes;
- provenance and algorithm metadata in active-step details;
- explicit algorithm names in the ingestion, analysis, graph, snapshot,
  rationale, query, and report steps;
- an analysis-node explanation that follows tokenization, TF-IDF, controlled
  SVO extraction, entity resolution, relation qualification, decision
  candidate extraction, and decision reduction;
- graph-node details that name Typed Evidence Graph Construction, PageRank,
  its fixed parameters, and `scoring-v1`;
- an explicit statement that the caller may use an external LLM, while every
  stored v0.4.0 base and overlay record originates from deterministic rules.

Badges must remain compact and must not replace the existing node-role legend.
The update must preserve flow playback, node exploration, keyboard behavior,
responsive layout, reduced-motion behavior, theme selection, and fullscreen.

## Standalone README

Create `README/architecture-v0.4.0.md` with these sections:

1. Purpose and scope
2. Provenance boundary
3. Components and responsibilities
4. End-to-end indexing pipeline
5. Algorithm registry
6. Typed graph and independent scoring dimensions
7. Immutable JSONL base snapshots
8. Bounded query behavior
9. Separate non-ranking rationale overlays
10. Cited report composition
11. Human authorization and engineering review
12. Current exclusions

The document links to `../architecture.html` and `../architecture.md`. It uses
declarative architecture prose rather than conversational corrections or
references to a prior discussion.

## Accuracy constraints

- Indexing analyzes the complete selected corpus. Query limits constrain only
  returned projections.
- Graph construction and scoring happen inside the `index` pipeline. The
  diagram's Build graph tab is a focused view, not a second persisted pass.
- The base snapshot contains graph and ranking records together. There is no
  preliminary ranking snapshot followed by a separate graph snapshot.
- Rationale resolution does not rerank the graph. Overlay records remain
  `rank_eligible: false`.
- Built-in report composition is deterministic. LLM interpretation begins only
  after the tool returns a bounded query result or cited report.
- Authorization and engineering review must not be labeled as algorithms.

## Validation

- Assert that the README exists at the requested path and links resolve.
- Check that every registered algorithm appears in the README and relevant
  diagram details.
- Verify deterministic/LLM/human labels agree across HTML and Markdown.
- Parse the inline JavaScript and validate all flow endpoints.
- Check for placeholders, remote runtime dependencies, and whitespace errors.
- Re-run mobile and desktop geometry/accessibility checks.
- Run the full repository test suite.
- Perform rendered browser inspection when a render-capable browser is
  available; otherwise record the limitation.
