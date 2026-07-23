# Architecture Graph v0.4.0 Interactive Diagram Design

**Date:** 2026-07-22  
**Audience:** Engineers learning or maintaining `architecture-graph-skill`

## Goal

Create an interactive, click-through explanation of the current v0.4.0
architecture. The diagram must explain both the repository's internal module
boundaries and its principal end-to-end workflows without presenting older
versions as a selectable mode.

## Deliverables

- `architecture.html`: self-contained interactive diagram based on the
  architecture-diagram template.
- `architecture.md`: companion description covering components, flow steps,
  invariants, and operational caveats.

Both files will live at the repository root.

## Topology

The canvas contains eight bounded component groups:

1. **Caller / Agent** — invokes the skill through the wrapper or CLI.
2. **CLI and capabilities** — parses commands, selects corpora and snapshots,
   and returns bounded envelopes or reports.
3. **Corpus and configuration** — discovers supported files, validates memory
   placement, and captures stable repository inputs.
4. **Ingestion** — turns Markdown, plaintext, JSON, YAML, Mermaid, and PlantUML
   into source, segment, evidence, derivation, and warning records.
5. **Deterministic analysis** — extracts terms, entities, claims, qualifiers,
   decision candidates, and reduced decisions.
6. **Graph and ranking** — constructs typed edges and calculates independent
   `scoring-v1` dimensions over the complete selected corpus.
7. **Snapshot memory** — validates and atomically publishes immutable JSONL
   snapshots plus the current pointer.
8. **Rationale overlay and presentation** — resolves decision-local rationale
   into a separate non-ranking overlay and composes it at query/report time.

The caller sits at the left, processing modules occupy the center, and
immutable memory plus presentation outputs sit at the right. The rationale
overlay is visually separated below the frozen base snapshot path.

## Interactive Flows

1. **Index corpus** — caller → CLI → corpus/config → ingestion → analysis →
   graph/ranking → snapshot memory → caller.
2. **Build and rank graph** — ingested records → deterministic analysis → typed
   graph → independent scores → immutable snapshot.
3. **Query architecture** — caller → CLI → snapshot reader → bounded semantic
   query → caller.
4. **Build rationale overlay** — caller → CLI → base snapshot → deterministic
   rationale resolver → contract validation → separate overlay publication.
5. **Produce composed report** — caller → CLI → base snapshot plus compatible
   overlay → query/report composition → cited report.

Each step will show a trimmed, realistic record or command payload and no more
than three metadata chips.

## Invariants to Emphasize

- Indexing and ranking operate over the complete selected corpus; response
  limits affect presentation only.
- Base snapshots are immutable and content-addressed.
- Semantic schema 2 and `scoring-v1` remain the frozen base contract.
- Rationale overlays are bound to an exact base snapshot and ranking digest.
- Overlay records are always `rank_eligible: false` and never enter TF-IDF,
  PageRank, graph edges, or decision scoring.
- Evidence and deterministic provenance remain traceable to source spans.
- Writes require ignored project-local memory or an explicitly managed memory
  root.

## Interaction and Presentation

- No mode toggle: the diagram presents only v0.4.0.
- Five flow tabs drive step-by-step animation and the details panel.
- Nodes remain clickable, draggable, keyboard accessible, and resettable.
- Dark and light themes remain available through the template's theme control.
- The layout favors minimal wire crossings and keeps overlay publication
  visibly distinct from base snapshot publication.

## Validation

- No unresolved template placeholders.
- Every flow begins with a clear source and ends with a user-visible result or
  persisted artifact.
- Every referenced node exists and participates in at least one flow.
- HTML inline JavaScript parses successfully.
- The generated page is rendered and visually inspected when browser tooling
  is available.
- The companion Markdown stands alone without requiring the HTML.
