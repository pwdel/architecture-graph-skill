# Architecture Graph v0.4.0 architecture guide

Architecture Graph turns an inspected repository into deterministic, evidence-backed architecture memory. The interactive [architecture.html](architecture.html) shows the same system as five clickable flows; this guide is the standalone explanation of its components, records, publication rules, and boundaries.

## Components

| Component | Modules | Responsibility | Key invariant |
| --- | --- | --- | --- |
| Agent / engineer (caller) | Wrapper or shell invocation; external to the package | Starts a bounded command and receives a JSON envelope or cited report. | The caller selects the corpus and response bounds; it does not bypass the CLI's capability and write guards. |
| CLI + capability gate | `cli.py`, `capabilities.py`, `errors.py` | Parses commands, selects snapshots and corpora, enforces capabilities and output bounds, and returns command results. | Commands make memory access explicit; a report or query is read-oriented unless the caller explicitly requests a write command. |
| Corpus + config | `corpus.py`, `config.py`, `sources.py`, `project.py` | Discovers supported inputs, resolves configuration, and verifies the project-local memory location. | A writable local memory directory must be ignored by the project or be an explicitly managed memory root. |
| Format ingestion | `ingest/markdown.py`, `ingest/plaintext.py`, `ingest/structured.py`, `ingest/diagrams.py` | Converts Markdown, plaintext, JSON, YAML, Mermaid, and PlantUML into source, segment, evidence, derivation, and warning records. | Evidence remains tied to source versions and spans; unsupported or partial inputs become warnings rather than invented facts. |
| Deterministic analysis | `analysis.py`, `terms.py`, `entities.py`, `claims.py`, `qualifiers.py`, `decision_candidates.py`, `decisions.py` | Extracts normalized terms, entities, claims, qualifiers, decision candidates, and reduced decisions. | Semantic schema 2 records are deterministic and retain derivation provenance. |
| Typed graph + scoring-v1 | `semantic_graph.py`, `relations.py`, `ranking.py` | Creates typed evidence-graph edges and independent score dimensions for the complete selected corpus. | `scoring-v1` dimensions are calculated independently; presentation limits never alter their inputs. |
| Immutable JSONL snapshots | `snapshot.py`, `jsonl_store.py`, `records.py`, `schemas.py` | Validates, content-addresses, and atomically publishes the deterministic base snapshot and current pointer. | A published deterministic snapshot is immutable; later reads validate its manifest and record contents. |
| Rationale overlay | `rationale_rules.py`, `rationale_resolver.py`, `overlay_contract.py`, `overlay_snapshot.py`, `overlay_types.py` | Resolves decision-local rationale and publishes a compatible, separate overlay. | Every overlay binds to one base snapshot and ranking digest; all overlay records are `rank_eligible: false`. |
| Bounded query + report | `query.py`, `paging.py`, `views.py`, `semantic_queries.py`, `overlay_queries.py`, `report.py` | Projects bounded semantic query envelopes and composes cited reports from the base and, when compatible, a rationale overlay. | Pagination and `max_chars` bound presentation only; rationale is composed at read time and never becomes a ranking input. |

## Flows

Each list follows the corresponding HTML tab and its `from` and `to` nodes. “Memory” means either the immutable deterministic base snapshot or the separately published rationale overlay.

### Index corpus (`index_corpus`)

1. **Agent / engineer → CLI + capability gate — invoke the index command.** The caller sends `architecture-graph index PATH --json`; no memory is read or written.
2. **CLI + capability gate → Corpus + config — select stable inputs.** The handoff carries the input path and memory-root configuration. It verifies memory placement but does not read or write snapshot records.
3. **Corpus + config → Format ingestion — ingest supported formats.** Source selections become source, segment, evidence, derivation, and warning records, including source version IDs and spans. No memory is read or written.
4. **Format ingestion → Deterministic analysis — analyze the record catalog.** Ingestion records become terms, entities, claims, qualifiers, decision candidates, and decisions such as a decision carrying `missing_rationale`. No memory is read or written.
5. **Deterministic analysis → Typed graph + scoring-v1 — create graph and scores.** Claims and evidence become typed edges and ranking records with independent dimensions such as `navigation` and `criticality`; no memory is read or written.
6. **Typed graph + scoring-v1 → Immutable JSONL snapshots — publish the base.** Validated JSONL records, manifest, semantic schema 2, and `scoring-v1` metadata are atomically **written** as an immutable deterministic snapshot.
7. **Immutable JSONL snapshots → Agent / engineer — return the index result.** The snapshot identity and bounded index summary are returned after publication; this is a result handoff, not an additional memory mutation.

### Build graph (`build_graph`)

1. **Format ingestion → Deterministic analysis — normalize ingestion records.** Sources, segments, evidence, derivations, and warnings form the phase-one catalog; no memory is read or written.
2. **Deterministic analysis → Typed graph + scoring-v1 — build evidence graph and rank decisions.** The analyzer emits typed edges such as `ASSERTS` and computes independent score dimensions over the full corpus; no memory is read or written.
3. **Typed graph + scoring-v1 → Immutable JSONL snapshots — freeze the graph.** Graph and ranking records are **written** into the immutable deterministic base snapshot, preserving the `scoring-v1` contract for later reads.

### Query architecture (`query_architecture`)

1. **Agent / engineer → CLI + capability gate — request a bounded query.** The caller supplies a command such as `architecture-graph decisions ROOT --limit 20 --max-chars 12000 --json`; no memory is read or written at this boundary.
2. **CLI + capability gate → Immutable JSONL snapshots — open a selected snapshot.** The CLI resolves the corpus and snapshot and **reads** the immutable base after integrity validation; it does not write memory.
3. **Immutable JSONL snapshots → Bounded query + report — project an envelope.** The query layer **reads** frozen decision and ranking records, then applies ordering, page limits, and character limits to produce items and a cursor. It does not write memory.
4. **Bounded query + report → Agent / engineer — return a traceable response.** The caller receives a bounded envelope with its snapshot binding and record identifiers; no memory is read or written.

### Build rationale overlay (`build_rationale`)

1. **Agent / engineer → CLI + capability gate — explicitly request rationale build.** The caller sends `architecture-graph rationale build ROOT --snapshot deterministic:… --json`; no memory changes at this boundary.
2. **CLI + capability gate → Immutable JSONL snapshots — load the exact base.** The selected deterministic base and its ranking digest are **read**; the base is never rewritten.
3. **Immutable JSONL snapshots → Rationale overlay — resolve decision-local rationale.** The resolver **reads** base decisions, evidence, diagnostics, and derivations and emits `rationale_resolution` records with `rank_eligible: false`; it does not change the base.
4. **Rationale overlay → Immutable JSONL snapshots — validate provenance and compatibility.** The overlay candidate is checked against the **read** base snapshot, ranking digest, evidence references, and derivation references. This validation does not write memory.
5. **Immutable JSONL snapshots → Rationale overlay — publish separately.** A compatible content-addressed overlay and its current pointer are **written** in overlay storage. The immutable base snapshot remains unchanged.
6. **Rationale overlay → Agent / engineer — return coverage.** The caller receives the overlay ID and resolved/missing coverage; no memory is changed.

This is the only flow that mutates the rationale overlay. During a report-only task, `rationale build` requires explicit user authorization: composing or reading a report must not silently create, replace, or publish overlay memory.

### Compose report (`compose_report`)

1. **Agent / engineer → CLI + capability gate — request a cited report.** The caller sends a bounded report command such as `architecture-graph report ROOT --max-chars 12000 --json`; no memory is read or written at this boundary.
2. **CLI + capability gate → Immutable JSONL snapshots — open the base.** The report path **reads** the immutable deterministic snapshot and leaves its graph, scores, and records untouched.
3. **Immutable JSONL snapshots → Rationale overlay — load only a compatible overlay.** The report path **reads** the separately stored overlay only after checking its exact base snapshot and ranking digest; an absent, stale, or mismatched overlay is not composed.
4. **Rationale overlay → Bounded query + report — compose assertions and citations.** Presentation **reads** the base and compatible overlay to add rationale to decision summaries while preserving base citations and `max_chars`; it writes no memory.
5. **Bounded query + report → Agent / engineer — deliver the report.** The caller receives a compact cited report with coverage and rationale-resolution status; no memory is read or written after rendering.

## Invariants

### Complete-corpus analysis; bounded presentation

Indexing, graph construction, and `scoring-v1` analyze the complete selected corpus. Query limits, paging cursors, selected fields, and `max_chars` constrain only the response envelope or report; they do not filter the corpus before ranking.

### Immutable deterministic snapshots

The deterministic base is validated JSONL plus a manifest, content-addressed identity, and current pointer. Publication is atomic, and readers validate snapshot contents. Semantic schema 2 and `scoring-v1` remain frozen base contracts.

### Independent scoring dimensions

Graph ranking stores separate score dimensions, including navigation and criticality, rather than collapsing unrelated signals into a response-dependent value. Scores are computed from the complete base corpus and are independent of pagination and presentation bounds.

### Evidence and derivation provenance

Ingestion records preserve source version IDs and spans. Analysis, graph records, decisions, and overlay validation retain references to the evidence and derivations that support them, so a result can be traced back to the source material instead of relying on an uncited summary.

### Separate non-ranking rationale overlays

A rationale overlay is distinct from the deterministic base and is bound to the exact base snapshot and ranking digest. Overlay records are always `rank_eligible: false`: they never enter TF-IDF, PageRank, typed graph edges, or decision scoring. The overlay can be composed into a report only after compatibility validation.

## Current exclusions

The v0.4.0 model deliberately excludes image interpretation, human review mutation, decision lineage, and semantic snapshot diff. Those are not implied by a snapshot, a query, a rationale overlay, or a composed report.
