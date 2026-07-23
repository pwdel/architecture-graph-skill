# Architecture Graph v0.4.0 Interactive Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a v0.4.0-only interactive architecture diagram and standalone companion guide for `architecture-graph-skill`.

**Architecture:** Adapt the installed architecture-diagram `assets/template.html` without replacing its interaction engine. Represent the repository as eight module groups and five ordered flows, keeping the immutable base snapshot path visually separate from the non-ranking rationale overlay path.

**Tech Stack:** Self-contained HTML, CSS, inline JavaScript, Markdown, existing architecture-diagram template, Node syntax checks, optional Puppeteer/Chromium screenshot verification.

## Global Constraints

- Create exactly `architecture.html` and `architecture.md` at the repository root.
- Present only architecture-graph v0.4.0; remove the mode selector entirely.
- Preserve template support for flow tabs, playback, node click/drag, keyboard navigation, layout reset, fullscreen, and dark/light theme.
- Show eight component groups and five flows from the approved design.
- Keep rationale overlays visibly separate from immutable base snapshots.
- State that semantic schema 2 and `scoring-v1` remain frozen and overlays are always `rank_eligible: false`.
- Keep payloads realistic and trimmed, with no more than three chips per step.
- Do not introduce external runtime dependencies; remove remote font links so the HTML works offline.

---

### Task 1: Build the Interactive v0.4.0 Diagram

**Files:**
- Create: `architecture.html`
- Read: `/Users/patrick/Projects/skills/architecture-diagram-skill/skills/architecture-diagram/assets/template.html`
- Read: `scripts/architecture_graph/cli.py`
- Read: `scripts/architecture_graph/indexer.py`
- Read: `scripts/architecture_graph/analysis.py`
- Read: `scripts/architecture_graph/semantic_graph.py`
- Read: `scripts/architecture_graph/ranking.py`
- Read: `scripts/architecture_graph/snapshot.py`
- Read: `scripts/architecture_graph/rationale_resolver.py`
- Read: `scripts/architecture_graph/overlay_snapshot.py`
- Read: `scripts/architecture_graph/semantic_queries.py`
- Read: `scripts/architecture_graph/report.py`

**Interfaces:**
- Consumes: the approved topology and flow contract in `docs/superpowers/specs/2026-07-22-v040-interactive-architecture-diagram-design.md`.
- Produces: a standalone `architecture.html` with node IDs `caller`, `cli`, `corpus`, `ingest`, `analysis`, `graph`, `memory`, `overlay`, and `presentation`, plus flow keys `index_corpus`, `build_graph`, `query_architecture`, `build_rationale`, and `compose_report`.

- [ ] **Step 1: Copy the complete diagram template**

Copy the installed template byte-for-byte to `architecture.html` as the starting point. Retain its CSS, SVG wire renderer, flow player, node click/drag handlers, keyboard shortcuts, fullscreen behavior, layout persistence, and theme switcher.

- [ ] **Step 2: Replace top-level presentation regions**

Set the title to `Architecture Graph v0.4.0 · Architecture`, the eyebrow to `DETERMINISTIC ARCHITECTURE MEMORY`, the heading to `Architecture Graph v0.4.0 · Evidence to decisions`, and the subtitle to `Click through indexing, deterministic analysis, immutable publication, bounded retrieval, and non-ranking rationale composition.` Remove the `.modepick` element and remove the `O mode` shortcut copy. Remove all three Google Fonts tags so the file is network-independent.

- [ ] **Step 3: Define the node topology**

Replace the template nodes with these exact IDs and responsibilities:

```text
caller        Agent / engineer                 far left, center
cli           CLI + capability gate            left-center, center
corpus        Corpus + config                   upper-left-center
ingest        Format ingestion                  upper-middle
analysis      Deterministic analysis            center
graph         Typed graph + scoring-v1          upper-right-center
memory        Immutable JSONL snapshots         far right, upper
overlay       Rationale overlay                 lower-right-center
presentation  Bounded query + report            far right, lower
```

Use existing template roles only: `user` for caller, `orch` for CLI and presentation, `embed` for corpus and ingestion, `compute` for analysis and graph, `vector` for memory, and `seed` for overlay. Place nodes so the base pipeline travels primarily left-to-right and the overlay path remains below it.

- [ ] **Step 4: Encode the five flows**

Define realistic steps with required `from`, `to`, `color`, `title`, `route`, `payload`, `desc`, and at most three `chips` values:

```text
index_corpus:
  caller -> cli -> corpus -> ingest -> analysis -> graph -> memory -> caller

build_graph:
  ingest -> analysis -> graph -> memory

query_architecture:
  caller -> cli -> memory -> presentation -> caller

build_rationale:
  caller -> cli -> memory -> overlay -> memory -> overlay -> caller

compose_report:
  caller -> cli -> memory -> overlay -> presentation -> caller
```

Payload examples must show actual command and record shapes such as:

```text
architecture-graph index PATH --json
{"kind":"decision","diagnostic_codes":["missing_rationale"]}
{"scores":{"navigation":0.31,"criticality":0.62},"rule_version":"scoring-v1"}
{"base_snapshot_id":"deterministic:…","rank_eligible":false}
{"base_diagnostics":["missing_rationale"],"active_diagnostics":[]}
```

- [ ] **Step 5: Make the template single-mode safe**

Update mode-dependent JavaScript so the absence of `.modepick button` elements is valid. Use one constant mode label, `v0.4.0`, in the side panel. Remove or neutralize the `O` shortcut without affecting the numeric flow shortcuts, theme toggle, fullscreen, playback, or node behavior.

- [ ] **Step 6: Run structural validation**

Run:

```bash
test -s architecture.html
! rg '\{\{' architecture.html
rg -n 'data-id="(caller|cli|corpus|ingest|analysis|graph|memory|overlay|presentation)"' architecture.html
rg -n 'index_corpus|build_graph|query_architecture|build_rationale|compose_report' architecture.html
! rg 'fonts\.googleapis|fonts\.gstatic' architecture.html
```

Expected: the file exists; no placeholder or remote-font searches produce output; all nine node IDs and five flow keys are present.

- [ ] **Step 7: Validate inline JavaScript syntax**

Extract the final inline script to a temporary file and run `node --check` against it. The command must exit 0 with no syntax errors. Confirm every `from` and `to` value resolves to an existing node ID by parsing the HTML node IDs and flow endpoints with a short read-only validation script.

- [ ] **Step 8: Commit the interactive diagram**

```bash
git add architecture.html
git commit -m "docs: add interactive v0.4.0 architecture diagram"
```

### Task 2: Add the Companion Architecture Guide and Visual QA

**Files:**
- Create: `architecture.md`
- Verify: `architecture.html`
- Read: `/Users/patrick/Projects/skills/architecture-diagram-skill/skills/architecture-diagram/references/screenshot.js`

**Interfaces:**
- Consumes: the exact node IDs, flow labels, step ordering, payloads, and invariants encoded in `architecture.html`.
- Produces: a standalone `architecture.md` that explains the same system without requiring the interactive page.

- [ ] **Step 1: Write the component guide**

Describe all nine displayed nodes in a component table with columns `Component`, `Modules`, `Responsibility`, and `Key invariant`. Map module families explicitly:

```text
CLI: cli.py, capabilities.py, errors.py
Corpus: corpus.py, config.py, sources.py, project.py
Ingestion: ingest/markdown.py, ingest/plaintext.py, ingest/structured.py, ingest/diagrams.py
Analysis: analysis.py, terms.py, entities.py, claims.py, qualifiers.py, decision_candidates.py, decisions.py
Graph: semantic_graph.py, relations.py, ranking.py
Memory: snapshot.py, jsonl_store.py, records.py, schemas.py
Overlay: rationale_rules.py, rationale_resolver.py, overlay_contract.py, overlay_snapshot.py, overlay_types.py
Presentation: query.py, paging.py, views.py, semantic_queries.py, overlay_queries.py, report.py
```

- [ ] **Step 2: Document every flow step-by-step**

Add five sections matching the HTML tabs. For each flow, list every handoff in order, identify the primary records crossing the boundary, and state whether the step reads or writes memory. Explain that `rationale build` is the only overlay-mutating flow and should require user authorization during a report-only task.

- [ ] **Step 3: Document invariants and known boundaries**

Include concise sections for:

```text
Complete-corpus analysis vs bounded presentation
Immutable deterministic snapshots
Independent scoring dimensions
Evidence and derivation provenance
Separate non-ranking rationale overlays
Current exclusions: image interpretation, human review mutation, decision lineage, semantic snapshot diff
```

- [ ] **Step 4: Validate Markdown/HTML agreement**

Run searches proving all five flow names and the snapshot/overlay invariants appear in both files. Run `git diff --check`. Expected: no missing flow names, no whitespace errors, and no unresolved template placeholders.

- [ ] **Step 5: Render and inspect the diagram**

If Chromium and `puppeteer-core` are available, run the installed `references/screenshot.js` against `architecture.html` and save previews under `/private/tmp/architecture-graph-diagram-preview/`. Inspect the default first flow and the composed-report flow at step 3 for overlaps, clipped labels, cramped payloads, and unnecessary wire crossings. Adjust node percentages in `architecture.html` and repeat until readable. If Puppeteer is unavailable, open the local file through the available browser controller and inspect the same flows.

- [ ] **Step 6: Final verification**

Run:

```bash
git diff --check
test -s architecture.html
test -s architecture.md
! rg '\{\{' architecture.html architecture.md
```

Expected: all commands succeed. Confirm the repository test suite remains unaffected because the deliverables are documentation-only.

- [ ] **Step 7: Commit the companion guide and any visual adjustments**

```bash
git add architecture.html architecture.md
git commit -m "docs: explain v0.4.0 architecture flows"
```
