# Architecture Graph Phase 2 Evidence Graph Design

**Date:** 2026-07-21  
**Branch:** `feat/phase-2-evidence-graph`  
**Baseline:** `v0.2.0`

## Problem

Phase 1 indexes architecture sources into bounded, source-backed evidence. A
real run against a 1,312-line design plan produced one source and 764 segments,
but no terms, claims, decisions, graph edges, or report. The agent queried empty
future record types, then used `jq`, `rg`, and broad source reads to reconstruct
the document.

That run proves the storage and retrieval foundation works. It also identifies
the Phase 2 requirement: reduce prose and text-native diagrams into a navigable,
ranked architecture graph without asking an LLM to scan the corpus.

Most architecture sources contain prose paragraphs, headings, lists, Mermaid,
and PlantUML. YAML and JSON may expose useful structure, but they cannot define
the semantic model. Phase 2 must treat format-specific structure as evidence
metadata and normalize every supported source into one claim and graph model.

## Scope

Phase 2 adds deterministic, offline analysis for:

- Markdown, ADRs, and architecture prose;
- selected plaintext;
- Mermaid and PlantUML;
- YAML and JSON;
- term and glossary discovery;
- conservative entities and qualified claims;
- typed evidence graphs and bounded traversal;
- navigation, criticality, review-priority, and confidence scores;
- source-anchored architecture decisions;
- evidence explanations and engineer reports.

Phase 2 excludes raster images, screenshots, scanned diagrams, visual PDF
interpretation, embeddings, vector databases, provider SDKs, live LLM calls,
and network access. A later phase may evaluate image support. Phase 2 does not
require it.

Human review mutation, semantic snapshot diff, and long-term decision lineage
remain later increments.

## Relationship to the Existing Phase 2 Plan

This design supersedes the release boundary and task order in
`docs/superpowers/plans/2026-07-19-architecture-graph-phase-2-analysis.md`.
Implementation planning may reuse its deterministic schemas, provenance rules,
scoring safeguards, and test fixtures. The new plan must move typed graph
construction and navigation ranking ahead of reporting, and move human review,
history, and semantic diff out of the first Phase 2 release.

## Principles

1. Prose and text-native diagrams share one semantic model.
2. Every claim, edge, score, decision, and report assertion resolves to source
   evidence and a persisted derivation.
3. Explicit structure raises confidence but does not create a separate JSON
   analysis path.
4. Graph centrality supports navigation. It does not define architectural
   importance.
5. Navigation, criticality, review priority, and extraction confidence remain
   independent scores.
6. Duplicate source bytes cannot increase corroboration or rank features.
7. Unaccepted proposals cannot become current commitments.
8. Similarity may suggest aliases but cannot merge entities.
9. Phase 2 analysis remains reproducible without a downloaded NLP model.

## Pipeline

```text
sources
  -> segments and diagram statements
  -> term discovery
  -> conservative entities
  -> qualified relations
  -> claims
  -> typed evidence graph
  -> navigation ranking
  -> decision reduction
  -> criticality, review-priority, and confidence scores
  -> bounded queries, explanations, and report
```

Each stage consumes immutable records from the prior stage and returns records
plus their derivations. The indexer remains the only snapshot publisher. A
material source change reruns every corpus-global stage before publication.

## Normalized Evidence

Phase 1 source adapters continue to own file parsing. Phase 2 consumes a common
evidence contract containing:

- source version and content hash;
- source path and exact span;
- segment or diagram-statement ID;
- original text or edge label;
- heading path and section role;
- source authority and document status;
- adapter and extraction method;
- optional format structure such as JSON pointer, YAML path, Mermaid node ID,
  or PlantUML participant;
- evidence and derivation IDs.

Prose paragraphs, list items, headings, diagram nodes, diagram edges, and
structured values retain their format-specific metadata. Later stages operate
on their normalized evidence fields rather than branching on the source format.

## Term Discovery and Glossary

`terms.py` discovers candidate vocabulary from:

- sparse TF-IDF across distinct source-content hashes;
- headings and explicit glossary sections;
- acronyms and declared aliases;
- repeated architecture nouns and noun phrases;
- Mermaid and PlantUML labels;
- structured field names and values when they carry architectural meaning.

TF-IDF discovers vocabulary and contributes a small lexical feature to
navigation. It cannot create a claim, promote a decision, or make a decision
critical.

Term records include canonical form, observed forms, evidence IDs, distinct
source count, discovery signals, and derivation IDs. Glossary candidates remain
separate from confirmed entities.

## Entities, Relations, and Claims

`entities.py` creates entities only from explicit IDs, declared aliases, exact
canonical keys, or unambiguous acronyms. Similarity emits an alias-candidate
warning.

`relations.py` extracts subject-predicate-object candidates from prose and
node-edge-node candidates from text-native diagrams. `qualifiers.py` attaches:

- modality;
- polarity;
- conditions;
- scope;
- time applicability;
- section role;
- source status and authority;
- parser provenance.

Incomplete tuples remain relation candidates with warnings. `claims.py`
promotes complete, qualified relations into claims. Claims retain their source
language, normalized predicate, arguments, qualifiers, evidence IDs, and
derivation IDs.

Diagram claims use the same schema as prose claims. Their provenance records
the diagram adapter. A diagram edge may corroborate prose, contradict it, or
stand alone; it does not outrank accepted ADR prose by format.

## Typed Evidence Graph

The graph contains these node types:

```text
source
segment
evidence
term
entity
claim
decision
warning
derivation
```

The graph uses typed edges:

```text
CONTAINS
MENTIONS
ASSERTS
SUBJECT_OF
OBJECT_OF
SUPPORTS
CONTRADICTS
QUALIFIES
DERIVED_FROM
RELATED_TO
```

Every semantic edge cites the claim or evidence that justifies it. Graph
records remain projection-independent. Queries build bounded projections from
persisted nodes and edges rather than storing a database.

## Ranking

Phase 2 persists four scores with separate feature vectors and derivations.

### Navigation

Navigation answers: "What should I inspect next?"

Features may include typed degree, bounded centrality, distinct source-content
hashes, cross-boundary connections, claim and decision participation, glossary
relevance, contradiction links, and lifecycle eligibility. Mention count alone
cannot dominate the score.

### Criticality

Criticality measures architectural consequence using authority, modality,
scope, affected boundaries, evidence breadth, and structural impact. A
low-degree atomicity or security constraint may rank as critical.

### Review priority

Review priority identifies missing rationale, contradictions, weak evidence,
unresolved scope, churn signals, and low-confidence commitments.

### Extraction confidence

Confidence measures interpretation reliability using parser provenance,
statement completeness, explicit structure, source quality, and independent
corroboration.

All features use versioned rules. Scores are finite, clamped to zero through
one, rounded canonically, and explainable through stored inputs. Duplicate
content contributes once.

## Decisions

`decisions.py` reduces source-anchored claims into conservative decision
records. Explicit ADR status and structured decision fields provide strong
signals, but prose claims follow the same reducer.

Decision identity does not depend on path spelling or mention count. Records
preserve status, scope, rationale evidence, consequence evidence, supporting
and contradicting claim IDs, source authority, and the four independent scores.

Proposals remain proposals until accepted source status or an authorized human
review promotes them. Missing rationale produces a diagnostic rather than
invented text.

## Commands

Phase 2 adds:

```bash
architecture-graph capabilities --json
architecture-graph terms ROOT --corpus ID --json
architecture-graph neighbors ROOT --corpus ID --node ID --depth 2 --json
architecture-graph decisions ROOT --corpus ID --score navigation --json
architecture-graph evidence ROOT --corpus ID --for ID --json
architecture-graph explain ROOT --corpus ID --id ID --json
architecture-graph report ROOT --corpus ID
```

`capabilities` reports implemented phases, commands, record types, provenance
layers, and unavailable features. Agents must not probe unavailable commands.

Every read command resolves one immutable snapshot, validates the selected
corpus, and returns complete bounded records. Common limits cover item count,
graph depth, evidence count, and character budget. Stable cursors bind the
snapshot, command, normalized arguments, fields, filters, score, and output
format.

Queries hydrate common provenance fields such as source path, span, segment
text, evidence IDs, and derivation IDs. Agents should not need broad source
reads merely to cite a result.

## Report

The engineer report contains:

- high-navigation nodes and why they connect the corpus;
- critical decisions and constraints;
- high-review-priority gaps;
- conflicts and weak rationale;
- unresolved scope;
- glossary candidates;
- important prose and diagram agreement or disagreement.

Every assertion links to evidence records with source path and span. Reports
state when extraction confidence is low. Empty semantic stages produce an
explicit capability or coverage section rather than silent empty results.

## Failure Handling

- A missing configured NLP model emits `model_unavailable` and activates
  versioned tokenizer and rule fallbacks. Indexing never downloads a model.
- Unsupported diagram syntax emits bounded source warnings.
- Incomplete relations remain candidates and cannot enter the claim ledger.
- Ambiguous aliases remain diagnostics.
- One malformed source preserves valid evidence from other sources.
- Invalid derived records abort publication before pointer or ledger changes.
- Missing provenance layers and unavailable commands return distinct errors.
- Phase 2 keeps Phase 1 snapshot publication atomicity.

## Testing

Acceptance corpora combine ordinary architecture Markdown, ADRs, plaintext,
Mermaid, PlantUML, YAML, and JSON. No format receives exclusive semantic
behavior.

Tests must prove:

- byte-identical deterministic output for identical inputs;
- useful fallback output without a downloaded language model;
- source-backed claims from prose and text-native diagrams;
- diagram and prose claims share schemas while retaining provenance;
- duplicate bytes cannot inflate terms, evidence breadth, edges, or scores;
- navigation ranking surfaces useful traversal nodes without defining
  criticality;
- low-degree hard constraints can rank highly for criticality;
- conflicts and missing rationale raise review priority;
- every decision, edge, rank feature, explanation, and report assertion
  resolves to evidence and derivations;
- queries obey item, graph-depth, evidence, and character limits;
- cursors never skip items after budget fitting;
- capabilities prevent agents from probing unavailable features;
- indexing opens no network socket and downloads no artifact.

## Release Boundary

Phase 2 is complete when a mixed prose-and-diagram corpus can be indexed and
explored through terms, neighbors, decisions, evidence, explain, and report
without an LLM scanning full source files. The generated graph must remain
useful when structured YAML and JSON sources are absent.
