# Architecture Graph Phase 2.1 Ranked Retrieval Design

**Date:** 2026-07-21  
**Baseline:** `v0.3.0`  
**Target:** `v0.3.1`

## Problem

A real run of `v0.3.0` against a 1,312-line structured architecture plan
successfully indexed the complete source into 764 segments, but exposed three
acceptance failures:

1. `terms` returned an empty page while reporting 1,374 omitted records because
   the first term record, including its complete evidence list, could not fit
   the response character budget.
2. `decisions` returned no records because scalar JSON segments were not
   reassembled into their parent decision objects before semantic reduction.
3. `report` expanded hundreds of evidence citations inline. The agent abandoned
   the graph-native output and reconstructed the report with broad `jq`, `rg`,
   and source reads.

These are retrieval and reduction failures, not reasons to analyze less of the
corpus. Phase 2.1 must preserve exhaustive deterministic analysis while making
the default views compact, ranked, explainable, and usable within an agent's
context window.

## Goals

- Analyze every eligible source, segment, term, phrase, claim, node, and edge in
  the selected corpus.
- Persist complete ranked records and their versioned feature vectors.
- Apply `limit` and `max_chars` only to response presentation.
- Return compact summary records that cannot become unusable merely because
  their evidence collections are large.
- Reconstruct decision candidates from prose, ADRs, JSON, YAML, and text-native
  diagrams through one normalized reducer contract.
- Keep extraction confidence, authority, completeness, criticality, review
  priority, and graph navigation rank independent and explainable.
- Produce a concise default report with stable references to a complete,
  paginated evidence appendix.
- Report coverage and degradation explicitly instead of silently returning
  empty semantic results.

## Non-Goals

- Raster image or screenshot interpretation.
- Embeddings, vector databases, provider SDKs, network calls, or LLM ranking.
- A single opaque score that combines every notion of importance.
- Loading an entire evidence appendix into the default report.
- Treating JSON as the canonical architecture-document format.

## Core Model: Analyze Fully, Present Selectively

Phase 2.1 separates three layers:

```text
complete selected corpus
  -> deterministic extraction and scoring
  -> complete persisted analysis records
  -> compact ranked transport views
  -> paginated detail and evidence on demand
```

Analysis has no term, node, edge, or decision count budget. The existing source
selection rules still define the corpus, and safety limits may reject malformed
or pathologically large inputs before publication. Once accepted, all eligible
content participates in extraction and ranking.

`limit` controls the number of summary records returned. `max_chars` controls
serialized response size. Neither option changes stored records, feature
values, ordering, or rank. The same snapshot and query parameters always
produce the same ordered results and cursors.

## Complete Records and Compact Views

Persisted semantic records retain complete evidence and derivation references.
Public list commands project them into bounded summaries.

A term summary contains:

```json
{
  "id": "term:...",
  "canonical_form": "frontend adapter",
  "rank": 4,
  "lexical_score": 0.82,
  "graph_score": 0.61,
  "document_frequency": 12,
  "occurrence_count": 31,
  "evidence_count": 19,
  "top_evidence_ids": ["evidence:a", "evidence:b"]
}
```

The summary must not embed unbounded arrays. The full record remains available
through `get`, while `evidence` and `explain` provide bounded provenance views.
The same projection rule applies to decisions, claims, entities, warnings, and
report assertions.

Pagination must satisfy these invariants:

- a nonempty remaining result set returns at least one compact item;
- every successful cursor advances;
- no item is skipped when shrinking a page;
- an individually oversized compact record produces a typed
  `record_too_large` error naming the record and minimum required size;
- an empty result means there are genuinely no matching records;
- omitted and truncated counts refer to compact query records, not hidden
  nested evidence.

## Deterministic Term and Phrase Ranking

Term discovery continues across the full corpus. Phase 2.1 extends its stored
features without using an LLM:

- sparse BM25 or TF-IDF lexical salience across distinct source-content hashes;
- document frequency and occurrence count;
- multi-word phrase frequency;
- heading, glossary, definition, acronym, diagram-label, and structured-key
  signals;
- typed graph degree and bounded PageRank;
- cross-boundary participation;
- claim and decision participation;
- contradiction and review links.

Scores remain independently named. A documented, versioned navigation formula
may combine normalized lexical and graph features for default ordering, but the
component features must be returned by `explain`.

Near-duplicate detection is a separate feature. Deterministic token shingles
and Jaccard similarity, with optional MinHash acceleration when needed, may
identify duplicate or near-duplicate passages. Duplicate content cannot add
corroboration or inflate ranking. Similarity does not determine architectural
importance and cannot merge terms or entities without an explicit rule.

Graph PageRank answers which concepts are structurally central. BM25 or TF-IDF
answers which vocabulary is distinctive. Co-occurrence answers which concepts
appear together. No one measure substitutes for the others.

## Format-Neutral Semantic Reduction

The semantic reducer converts normalized evidence into conservative, typed
architecture records. Adapters retain format structure, but the reducer does
not define a JSON-only semantic path.

Before decision reduction, adapters emit candidate groups:

- Markdown and prose: heading scope, paragraph adjacency, explicit decision
  labels, modal language, and ADR metadata;
- JSON and YAML: values grouped by their nearest object or mapping parent, with
  recognized sibling roles such as `title`, `status`, `decision`, `rationale`,
  `consequences`, and `scope`;
- Mermaid and PlantUML: labeled nodes and edges grouped by diagram scope, with
  decision status only when explicitly stated;
- ADRs: document identity, lifecycle status, decision section, rationale, and
  consequences.

Each candidate group becomes a normalized `DecisionCandidate` containing
source spans, field roles, parser provenance, scope anchors, and explicit text.
The reducer may normalize status and predicates, but it cannot invent missing
rationale, consequences, or scope.

Candidate grouping uses deterministic anchors in descending strength:

1. explicit ADR or decision identifier;
2. common structured-object parent;
3. explicit decision heading and its bounded section;
4. normalized title plus compatible scope and lifecycle;
5. otherwise, separate candidates with a diagnostic.

## Decision Measures

There is no single `decision_confidence` score. Phase 2.1 persists independent
measures with feature vectors and derivations:

### Extraction confidence

Measures how reliably the record was recognized and assembled. Explicit ADR
fields and structured sibling roles are strong signals; heading-scoped modal
prose is moderate; loose lexical heuristics are weaker.

### Corroboration

Measures agreement across distinct source-content hashes. Duplicate bytes
count once. Contradictory evidence is recorded separately and cannot increase
corroboration.

### Authority and lifecycle

Represents accepted, approved, proposed, draft, deprecated, or observed status
from explicit source evidence. It is categorical metadata with an optional
versioned ordering for queries, not extraction confidence.

### Completeness

Records the presence of title, decision statement, status, rationale,
consequences, scope, owner, and date. Missing fields create diagnostics rather
than synthesized content.

### Criticality

Measures architectural consequence using scope, affected boundaries, security
or data-integrity impact, reversibility, structural impact, and authoritative
modality. A low-degree atomicity constraint may be more critical than a highly
connected glossary term.

### Review priority

Ranks contradictions, missing rationale, unresolved scope, lifecycle conflict,
weak extraction, or uncorroborated high-impact commitments.

### Navigation rank

Ranks records for exploration using typed connectivity, lexical salience,
cross-boundary links, and eligible lifecycle signals. It must not be presented
as criticality or authority.

All numeric scores are finite, normalized, canonically rounded, and generated
by versioned rules. `explain <record-id>` returns the component inputs, formula
version, resulting score, and supporting derivation IDs.

## Layered Report and Evidence Appendix

The default report is a navigation product, not a dump of every evidence span.
It uses adaptive sections with deterministic minimums and maximums, bounded by
a hard output ceiling.

The report contains:

- corpus coverage and parser diagnostics;
- executive architecture summary;
- highest-ranked accepted and proposed decisions;
- major boundaries and relationships;
- critical risks, contradictions, and missing rationale;
- key glossary candidates;
- recommended review questions.

Each assertion includes at most two representative citations and a stable
evidence count, such as `2 shown, 17 additional`. Representative citations are
selected deterministically by authority, distinct source content, extraction
confidence, and source order.

Complete provenance remains accessible as an evidence appendix through bounded
machine-readable queries. The appendix contains:

- every report assertion and its complete evidence IDs;
- complete decision and term evidence;
- ranking feature vectors and derivations;
- contradictions, warnings, and coverage diagnostics.

The CLI should expose one concise default rather than encouraging agents to
request exhaustive output accidentally:

```text
architecture-graph report <target>
architecture-graph report <target> --json
architecture-graph evidence <record-or-assertion-id> --cursor ...
architecture-graph explain <record-id>
```

`report --json` returns bounded assertions and appendix references. It does not
inline the complete appendix. A future explicit export option may write the
complete appendix to a file, but it is not required for Phase 2.1.

## Coverage and Failure Semantics

Every semantic command returns coverage metadata:

- selected and successfully parsed source counts;
- eligible segment count;
- candidate and reduced record counts;
- unsupported or degraded adapter counts;
- warning count;
- ranking and reducer rule versions.

If a corpus has eligible decision candidates but reduces none, `decisions` and
`report` must surface a diagnostic explaining why. `capabilities --json` must
emit a valid envelope or exit nonzero; successful silence is invalid.

An agent should never have to infer whether an empty list means no matches, an
oversized record, an unsupported format, or a failed reducer.

## Compatibility

- Existing snapshot IDs remain deterministic for unchanged Phase 1 records.
- Phase 2.1 analysis changes require a new analysis/ranking schema version and
  therefore new semantic record and snapshot identities where appropriate.
- Existing `get`, `find`, `terms`, `decisions`, `evidence`, `explain`, and
  `report` command names remain available.
- Default list output becomes compact. Complete stored records remain
  accessible through explicit detail queries.
- Cursor bindings include projection and scoring versions so cursors cannot be
  reused across incompatible views.

## Validation

Acceptance tests must include:

1. a corpus whose highest-ranked term has thousands of evidence IDs and still
   returns a nonempty compact first page;
2. stable full-corpus term ordering across repeated runs and different query
   page sizes;
3. cursor progress without skips or duplicates under tight character limits;
4. a structured JSON decision log reconstructed into decision records;
5. equivalent decision candidates from Markdown, YAML, JSON, and an ADR;
6. independent score assertions showing extraction confidence does not imply
   criticality or authority;
7. duplicate sources that do not inflate frequency, corroboration, or rank;
8. a default report that stays within its output ceiling and uses bounded
   representative citations;
9. complete evidence retrieval through the appendix path;
10. explicit diagnostics for zero reduced decisions and silent capability
    failures;
11. a regression fixture modeled on the 764-segment design plan;
12. an end-to-end agent acceptance test proving the report can be produced
    without broad fallback reads.

## Success Criteria

Phase 2.1 succeeds when the same real-world architecture plan produces:

- nonempty, deterministically ranked term summaries;
- reconstructed decision records with explainable independent measures;
- a concise default report within its declared output ceiling;
- complete provenance available through stable appendix references;
- explicit coverage diagnostics; and
- no need for the consuming agent to abandon graph-native retrieval for an
  unbounded source scan.
