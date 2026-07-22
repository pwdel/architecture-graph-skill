# Architecture Graph Rationale Overlay Contract Design

**Date:** 2026-07-22  
**Baseline:** `v0.3.1`  
**Target:** `v0.4.0`

## Problem

Architecture Graph v0.3.1 successfully indexed and queried a 764-segment
structured design plan, extracted seven decisions, produced bounded reports,
and kept the consuming agent graph-native. It also marked sampled decisions
with `missing_rationale` even though their structured objects contained
decision-local `context` fields that served as rationale.

Correcting this classification by changing existing decision records would
also change completeness and review-priority inputs. Adding new graph edges
could change PageRank even if the scoring formula stayed untouched. The
current ranking results are useful and must remain reproducible.

The next increment therefore adds deterministic rationale interpretation as a
separate overlay bound to an immutable v0.3.1 base snapshot. It does not rewrite
decisions, rankings, edges, or scoring inputs.

## Goals

- Recognize explicit and aliased rationale evidence deterministically.
- Preserve existing semantic-schema-v2 decision, ranking, and edge records
  byte-for-byte.
- Preserve `scoring-v1` formulas, inputs, rule resources, and ranking results.
- Publish rationale results as a separate, versioned, source-backed overlay.
- Make it structurally impossible for rationale overlays to participate in
  ranking.
- Compose validated overlays into `decisions`, `explain`, and `report` views.
- Preserve exact base-record access and expose the original diagnostic audit
  trail.
- Resolve false `missing_rationale` presentation warnings without deleting the
  original base diagnostic.

## Non-Goals

- Changing TF-IDF, PageRank, navigation order, score weights, or score features.
- Adding rank-eligible graph nodes or edges.
- Rebuilding or rewriting semantic-schema-v2 base snapshots.
- General typed links among boundaries, workstreams, risks, and use cases.
- LLM prompts, embeddings, semantic similarity, or provider calls.
- Inferring rationale that is not explicitly present in bounded source
  evidence.
- Decision lineage, review mutation, or semantic snapshot diff.

## Frozen Baseline Contract

The following v0.3.1 artifacts form the frozen base:

```text
semantic schema: 2
scoring rules: scoring-v1
decisions.jsonl
rankings.jsonl
edges.jsonl
base snapshot identity and manifest
```

For a fixed corpus and configuration, adding a rationale overlay must leave
`decisions.jsonl`, `rankings.jsonl`, and `edges.jsonl` byte-identical. The base
snapshot ID and ranking digest must remain unchanged.

The freeze applies to observable behavior and persisted records rather than
prohibiting all maintenance of the underlying source code. Security fixes,
compatibility repairs, and behavior-preserving refactors remain possible, but
golden tests must prove that they preserve the frozen artifacts.

## Architecture

```text
immutable semantic-schema-v2 base snapshot
  -> bounded decision and evidence reader
  -> deterministic rationale candidate discovery
  -> rationale resolution
  -> overlay contract validation
  -> atomic rationale-overlay publication
  -> optional query/report composition
```

The base snapshot remains independently usable. Overlay construction is an
explicit operation that reads the base but cannot publish through the base
snapshot writer.

## Overlay Storage

Rationale overlays live in a separate snapshot namespace beneath the selected
corpus memory. A conceptual layout is:

```text
.architecture-graph/corpora/<corpus-id>/
  snapshots/<base-snapshot-id>/
  overlays/rationale/<overlay-id>/
    MANIFEST.json
    rationale-resolutions.jsonl
    derivations.jsonl
    warnings.jsonl
  overlays/rationale/CURRENT
```

The overlay manifest contains:

- overlay schema version;
- overlay snapshot ID;
- exact base snapshot ID;
- exact base material-input digest;
- exact base ranking digest;
- rationale rule version and digest;
- overlay content digest;
- publication metadata required by the existing deterministic publisher.

An overlay cannot be attached to another base snapshot, even if record IDs
appear compatible.

## Rationale Resolution Contract

Each decision receives exactly one rationale-resolution record for a given
base snapshot and rule version:

```json
{
  "id": "rationale-resolution:...",
  "kind": "rationale_resolution",
  "schema_version": 1,
  "base_snapshot_id": "deterministic:...",
  "decision_id": "decision:...",
  "decision_content_digest": "sha256:...",
  "normalized_role": "rationale",
  "observed_roles": ["context"],
  "classification": "recognized_alias",
  "evidence_ids": ["evidence:..."],
  "resolves_diagnostics": ["missing_rationale"],
  "rule_version": "rationale-rules-v1",
  "rank_eligible": false,
  "derivation_ids": ["derivation:..."]
}
```

Valid classifications are:

- `explicit`: an explicit `rationale` field or section;
- `recognized_alias`: a versioned alias in an eligible decision-local scope;
- `ambiguous`: multiple incompatible rationale candidates;
- `missing`: no eligible rationale evidence.

The contract requires:

- an existing base snapshot;
- an existing decision in that snapshot;
- an exact matching decision content digest;
- resolvable evidence and derivation references;
- `normalized_role` equal to `rationale`;
- canonically ordered, unique observed roles and references;
- a supported rule version;
- `rank_eligible` exactly `false`;
- no rank-eligible node or edge records in the overlay;
- one canonical resolution per decision and rule version.

Validation rejects the complete overlay publication if any invariant fails.

## Deterministic Rationale Rules

`rationale-rules-v1.json` defines aliases, scope rules, precedence, and
classification values. The initial mapping is:

```text
rationale       -> explicit
reason          -> recognized_alias
reasons         -> recognized_alias
justification   -> recognized_alias
context         -> recognized_alias
why             -> recognized_alias
```

`why_now` is not globally treated as decision rationale. It is eligible only
when it is structurally local to one decision and the versioned rule explicitly
allows that location. A document-level `why_now` remains plan context.

Candidate precedence is:

1. explicit decision-local `rationale` field or section;
2. recognized structured sibling alias;
3. recognized bounded prose or ADR section;
4. multiple compatible candidates;
5. incompatible candidates classified as ambiguous;
6. no candidates classified as missing.

Multiple compatible passages may be aggregated. Conflicting passages remain
separate evidence references under an `ambiguous` resolution. The resolver
never synthesizes rationale text.

## Components

### `rationale_rules.py`

Loads and validates the versioned rule resource. It exposes exact alias,
location, precedence, and classification decisions. It contains no ranking or
graph-scoring behavior.

### `rationale_resolver.py`

Reads base decisions and bounded evidence, discovers rationale candidates,
applies rule precedence, and produces resolution, warning, and derivation
records.

### `overlay_contract.py`

Validates rationale records, base references, content digests, rule versions,
canonical collections, and the non-ranking invariant.

### `overlay_snapshot.py`

Publishes overlays atomically in their separate namespace. It verifies the
base snapshot before staging and immediately before pointer advancement.

### `overlay_queries.py`

Loads a compatible overlay and composes presentation records without changing
the underlying catalog. It exposes base diagnostics, active diagnostics, and
rationale resolution summaries.

## Commands

Overlay construction and inspection are explicit:

```bash
architecture-graph rationale build ROOT \
  --corpus CORPUS_ID \
  --snapshot BASE_SNAPSHOT_ID \
  --json

architecture-graph rationale status ROOT \
  --corpus CORPUS_ID \
  --snapshot BASE_SNAPSHOT_ID \
  --json

architecture-graph rationale find ROOT \
  --corpus CORPUS_ID \
  --classification recognized_alias \
  --json
```

`decisions`, `explain`, and `report` compose the compatible current rationale
overlay by default. They expose both historical and active interpretation:

```json
{
  "base_diagnostics": ["missing_rationale"],
  "active_diagnostics": [],
  "rationale_resolution": {
    "classification": "recognized_alias",
    "observed_roles": ["context"],
    "evidence_count": 1,
    "rule_version": "rationale-rules-v1"
  }
}
```

`--base-only` disables composition for `decisions`, `explain`, and `report`.
Exact `get decisions` access is always base-only and never silently composes
derived state.

## Diagnostic Semantics

The overlay does not delete or rewrite `missing_rationale` in a base decision.
Composition separates:

- `base_diagnostics`: immutable original diagnostics;
- `resolved_diagnostics`: base diagnostics resolved by a valid overlay;
- `active_diagnostics`: base diagnostics minus resolved diagnostics, plus any
  overlay diagnostics.

A report with a recognized `context` alias says that rationale was recognized
through `context`; it does not present `missing_rationale` as an active defect.
The base diagnostic remains available through base-only and audit views.

## Failure Handling

Overlay publication aborts when:

- the base snapshot or decision digest changed;
- evidence or derivation references are absent;
- rules emit an unsupported role or classification;
- any record or edge is rank-eligible;
- canonical ordering or uniqueness fails;
- the base snapshot changes during publication;
- the overlay would replace or mutate base files.

Ambiguous or missing rationale is valid semantic output and does not abort
publication. If no decisions exist, the overlay publishes an explicit empty
coverage result. Status and build commands report counts for decisions
examined, explicit, recognized aliases, ambiguous, missing, and warnings.

No command downloads a model, opens a network socket, or invokes an LLM.

## Compatibility and Versioning

```text
package version:           0.4.0
base semantic schema:      2
scoring rules:             scoring-v1
rationale overlay schema:  1
rationale rules:           rationale-rules-v1
```

Semantic-schema-v2 snapshots remain readable and do not need migration.
Repositories without a rationale overlay retain v0.3.1 query behavior. An
incompatible or stale overlay is ignored only when the command explicitly
allows base-only fallback; otherwise composition reports a typed compatibility
error rather than silently applying it.

## Contract-First Implementation Order

1. Define overlay record and manifest schemas.
2. Write failing immutability and reference-validation tests.
3. Implement overlay validation and non-ranking enforcement.
4. Implement atomic overlay storage bound to a base snapshot.
5. Write alias and scope-resolution tests.
6. Implement deterministic rationale discovery and resolution.
7. Implement base-plus-overlay query composition.
8. Add CLI commands and base-only controls.
9. Run the real design-plan regression and release verification.

No resolver behavior is implemented before the contract can reject mutations,
stale references, and rank-eligible overlay content.

## Acceptance Tests

Tests must prove:

- base decision, ranking, and edge files remain byte-identical;
- base snapshot ID and ranking digest remain unchanged;
- identical inputs produce byte-identical overlays;
- an overlay cannot bind to another base snapshot;
- a changed decision digest invalidates its resolution;
- missing evidence or derivations abort publication;
- `rank_eligible: true` is rejected;
- overlay nodes and edges cannot enter PageRank or scoring inputs;
- explicit `rationale` is classified as explicit;
- `context`, `reason`, `reasons`, `justification`, and eligible `why` fields are
  recognized aliases;
- top-level `why_now` is not attached to individual decisions;
- decision-local `why_now` follows the exact scoped rule;
- compatible passages aggregate and conflicts become ambiguous;
- genuine absence becomes missing;
- composed reports suppress resolved active warnings while retaining the base
  audit trail;
- `--base-only` reproduces v0.3.1 presentation;
- semantic-schema-v2 snapshots remain readable;
- repositories without overlays retain v0.3.1 behavior;
- the 764-segment design-plan regression preserves all seven base decisions and
  every ranking record while resolving false rationale diagnostics.

## Success Criteria

The increment succeeds when the real design plan gains source-backed rationale
resolutions for its decision-local `context` fields, current reports stop
presenting those decisions as actively missing rationale, and every v0.3.1
decision, edge, ranking, score, and rank order remains unchanged and auditable.
