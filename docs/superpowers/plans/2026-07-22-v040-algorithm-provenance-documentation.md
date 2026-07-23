# Architecture Graph v0.4.0 Algorithm Provenance Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a professional v0.4.0 architecture reference and update the interactive diagram so every algorithm, external LLM boundary, and human governance control has an accurate provenance label.

**Architecture:** Preserve the existing nine-node topology and five interactive flows. Add a small provenance vocabulary shared by the README, diagram nodes, and flow-step metadata; keep formal rule identifiers distinct from descriptive implementation labels. Enforce the documentation contract with repository tests so future diagram edits cannot silently reclassify deterministic work as LLM-generated.

**Tech Stack:** Markdown, self-contained HTML/CSS/vanilla JavaScript, Python 3.12, pytest, standard-library `pathlib` and `re`.

## Global Constraints

- Create `README/architecture-v0.4.0.md`; retain root `architecture.html` and `architecture.md`.
- Preserve all nine nodes, five flows, 25 ordered steps, playback, node exploration, dragging, keyboard controls, theme selection, fullscreen, reduced-motion behavior, and responsive layout.
- Use exactly three provenance categories: `Deterministic`, `Optional external LLM`, and `Human/control`.
- State that architecture-graph v0.4.0 makes no internal LLM calls.
- Treat authorization and engineering review as governance controls, never algorithms.
- Use existing rule, resource, derivation, and schema identifiers as authoritative names.
- Present unversioned algorithm names as descriptive implementation labels, not compatibility contracts.
- Indexing and ranking cover the complete selected corpus; response limits apply only during projection and reporting.
- Graph construction and scoring occur within one index operation and publish one immutable deterministic base snapshot.
- Rationale overlays bind to an exact base snapshot and ranking digest, remain separate, and are always `rank_eligible: false`.
- Do not add external runtime dependencies to `architecture.html`.

---

### Task 1: Standalone v0.4.0 architecture reference

**Files:**
- Create: `README/architecture-v0.4.0.md`
- Modify: `architecture.md`
- Create: `tests/test_architecture_documentation.py`

**Interfaces:**
- Consumes: the approved algorithm registry in `docs/superpowers/specs/2026-07-22-v040-algorithm-provenance-documentation-design.md`.
- Produces: `README/architecture-v0.4.0.md` as the canonical long-form architecture explanation; `architecture.md` links readers to it; `ALGORITHM_LABELS` and `PROVENANCE_LABELS` in the test module become the cross-artifact contract used by Task 2.

- [ ] **Step 1: Add failing documentation contract tests**

Create `tests/test_architecture_documentation.py` with:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README" / "architecture-v0.4.0.md"
DIAGRAM = ROOT / "architecture.html"
COMPANION = ROOT / "architecture.md"

PROVENANCE_LABELS = (
    "Deterministic",
    "Optional external LLM",
    "Human/control",
)

ALGORITHM_LABELS = (
    "Rule Tokenization",
    "Sparse TF-IDF Term Discovery",
    "Controlled SVO Relation Extraction",
    "Exact-Key Entity Resolution",
    "Relation Qualification",
    "Decision Candidate Extraction",
    "Decision Reduction",
    "Typed Evidence Graph Construction",
    "PageRank",
    "Independent Dimension Scoring",
    "Decision-Local Rationale Resolution",
    "Rationale Overlay Contract Validation",
    "Canonical Content-Addressed Publication",
    "Stable Bounded Projection",
    "Cited Report Composition",
)


def test_v040_readme_is_standalone_and_links_companions() -> None:
    text = README.read_text()
    assert text.startswith("# Architecture Graph v0.4.0 Architecture")
    assert "../architecture.html" in text
    assert "../architecture.md" in text
    for heading in (
        "## Purpose and scope",
        "## Provenance boundary",
        "## Components and responsibilities",
        "## End-to-end indexing pipeline",
        "## Algorithm registry",
        "## Typed graph and independent scoring",
        "## Immutable JSONL base snapshots",
        "## Bounded queries",
        "## Rationale overlays",
        "## Cited report composition",
        "## Authorization and engineering review",
        "## Current exclusions",
    ):
        assert heading in text


def test_v040_readme_names_algorithms_and_provenance() -> None:
    text = README.read_text()
    for value in (*PROVENANCE_LABELS, *ALGORITHM_LABELS):
        assert value in text
    for identifier in (
        "`rule_tokenizer`",
        "`sparse_tfidf`",
        "`terms-en-v1`",
        "`predicates-v1`",
        "`extraction-rules-en-v1`",
        "`entity-rules-v1`",
        "`exact_entity_key`",
        "`decision-rules-v1`",
        "`decision_reducer`",
        "`scoring-v1`",
        "`rationale-rules-v1`",
    ):
        assert identifier in text
    assert "does not call an LLM internally" in text
    assert "damping factor of `0.85`" in text
    assert "24 iterations" in text
    assert "rank_eligible: false" in text


def test_companion_links_to_long_form_reference() -> None:
    text = COMPANION.read_text()
    assert "README/architecture-v0.4.0.md" in text
```

- [ ] **Step 2: Run the contract tests and confirm the missing README failure**

Run:

```bash
UV_CACHE_DIR=/private/tmp/architecture-graph-uv-cache uv run pytest \
  tests/test_architecture_documentation.py -q
```

Expected: FAIL with `FileNotFoundError` for `README/architecture-v0.4.0.md`.

- [ ] **Step 3: Write the standalone architecture reference**

Create `README/architecture-v0.4.0.md`. Use the section names asserted above and include:

```markdown
# Architecture Graph v0.4.0 Architecture

Architecture Graph converts selected architecture sources into immutable,
evidence-backed memory that engineers and external agents can query without
loading the full corpus. The [interactive diagram](../architecture.html)
provides a step-by-step view. The shorter [diagram companion](../architecture.md)
lists the same five flows.

## Provenance boundary

Architecture Graph v0.4.0 does not call an LLM internally. Ingestion,
tokenization, TF-IDF, controlled SVO extraction, entity resolution, decision
reduction, graph construction, PageRank, scoring, rationale resolution,
validation, bounded retrieval, and built-in report composition are
deterministic. An external agent may use an LLM to interpret returned records
or reports, but that interpretation does not enter the immutable base or the
rationale overlay.
```

Complete the remaining required sections with the approved registry. For each algorithm row, provide the display name, existing identifier or fixed parameters, provenance, and naming status (`formal existing identifier`, `standard named algorithm`, or `descriptive implementation label`). Explain these facts directly:

- `index` performs ingestion, semantic analysis, graph construction, scoring, validation, and publication in one operation;
- Sparse TF-IDF uses term frequency and inverse document frequency over the complete selected corpus;
- Controlled SVO extraction directly uses canonical surfaces from `predicates-v1` plus fixed code rules rather than an LLM parser;
- Exact-Key Entity Resolution records `exact_entity_key`; `extraction-rules-en-v1` and `entity-rules-v1` are advertised pipeline resources but are not directly loaded by the current relation extractor or entity resolver;
- Typed Evidence Graph Construction emits `CONTAINS`, `MENTIONS`, `ASSERTS`, `SUBJECT_OF`, `OBJECT_OF`, and `SUPPORTS` edges;
- PageRank uses a damping factor of `0.85` and 24 iterations;
- `scoring-v1` keeps navigation, criticality, review priority, extraction confidence, corroboration, and completeness independent;
- the base snapshot publishes graph and ranking records together;
- query limits and `max_chars` bound presentation only;
- rationale resolution uses decision-local evidence and never reranks;
- report composition reads the base and only a compatible overlay;
- write authorization and engineering review are human controls.

- [ ] **Step 4: Link the concise companion to the long-form reference**

Add this paragraph after the opening paragraph of `architecture.md`:

```markdown
The long-form [v0.4.0 architecture reference](README/architecture-v0.4.0.md)
documents algorithm identifiers, deterministic provenance, the optional
external-LLM boundary, and human governance controls.
```

- [ ] **Step 5: Run focused tests and prose checks**

Run:

```bash
UV_CACHE_DIR=/private/tmp/architecture-graph-uv-cache uv run pytest \
  tests/test_architecture_documentation.py -q
git diff --check
rg -n 'TBD|TODO|PLACEHOLDER|\{\{' \
  README/architecture-v0.4.0.md architecture.md
```

Expected: 3 tests pass; `git diff --check` and the placeholder scan produce no output.

- [ ] **Step 6: Commit the architecture reference**

```bash
git add README/architecture-v0.4.0.md architecture.md \
  tests/test_architecture_documentation.py
git commit -m "docs: explain v0.4.0 algorithms and provenance"
```

---

### Task 2: Provenance-aware interactive architecture diagram

**Files:**
- Modify: `architecture.html`
- Modify: `tests/test_architecture_documentation.py`

**Interfaces:**
- Consumes: `ALGORITHM_LABELS` and `PROVENANCE_LABELS` from Task 1; the existing `flows` object, node IDs, player, details panel, and responsive topology in `architecture.html`.
- Produces: provenance-labelled nodes and step records; `step.provenance: string` and `step.method: string` become required flow-step fields rendered by the details panel.

- [ ] **Step 1: Add failing diagram provenance tests**

Append these tests to `tests/test_architecture_documentation.py`:

```python
import re


def test_diagram_exposes_provenance_categories_and_algorithm_registry() -> None:
    text = DIAGRAM.read_text()
    for value in (*PROVENANCE_LABELS, *ALGORITHM_LABELS):
        assert value in text
    assert "v0.4.0 makes no internal LLM calls" in text
    assert 'data-provenance="human optional-external-llm"' in text
    assert text.count('data-provenance="deterministic"') == 8


def test_every_flow_step_declares_provenance_and_method() -> None:
    text = DIAGRAM.read_text()
    flow_source = text.split("const flows = {", 1)[1].split("const SINGLE_MODE", 1)[0]
    step_count = len(re.findall(r'\{\s*from:"', flow_source))
    provenance_count = len(re.findall(r'provenance:"(?:Deterministic|Optional external LLM|Human/control)"', flow_source))
    method_count = len(re.findall(r'method:"[^"]+"', flow_source))
    assert step_count == 25
    assert provenance_count == step_count
    assert method_count == step_count


def test_diagram_keeps_existing_topology_and_offline_contract() -> None:
    text = DIAGRAM.read_text()
    assert text.count('class="node"') == 9
    assert text.count('class="flowtab"') == 5
    assert "https://fonts.googleapis.com" not in text
    assert "<script src=" not in text
```

- [ ] **Step 2: Run the focused tests and confirm provenance failures**

Run:

```bash
UV_CACHE_DIR=/private/tmp/architecture-graph-uv-cache uv run pytest \
  tests/test_architecture_documentation.py -q
```

Expected: the three Task 1 tests pass; the new diagram provenance tests fail because the badges and flow-step fields do not exist.

- [ ] **Step 3: Add the provenance legend and node badges**

Extend the existing controls area with an accessible provenance legend. Use the exact visible labels `Deterministic`, `Optional external LLM`, and `Human/control`, followed by this statement:

```html
<p class="provenance-note">v0.4.0 makes no internal LLM calls. LLM interpretation is optional and external to stored architecture memory.</p>
```

Add `data-provenance="human optional-external-llm"` to the caller node and `data-provenance="deterministic"` to each of the other eight nodes. Render compact badges inside nodes:

```html
<div class="provenance-badges" aria-label="Provenance">
  <span class="provenance human">Human/control</span>
  <span class="provenance llm">Optional external LLM</span>
</div>
```

Internal nodes render one `Deterministic` badge. Add CSS tokens and light-theme styles for all three badge types without changing node role colors or node geometry.

- [ ] **Step 4: Add algorithm and provenance fields to all 25 steps**

Extend the documented flow-step schema with required `provenance` and `method` fields. Use `Human/control` for explicit command invocation or authorization handoffs and `Deterministic` for processing, built-in rendering, and delivery of results. Do not label a delivery step `Optional external LLM`: optional LLM interpretation starts only after delivery and is represented by the caller node and provenance legend, outside the 25 tool-executed steps.

Use these method labels at the relevant internal steps:

```text
Rule Tokenization
Sparse TF-IDF Term Discovery
Controlled SVO Relation Extraction
Exact-Key Entity Resolution
Relation Qualification
Decision Candidate Extraction
Decision Reduction
Typed Evidence Graph Construction
PageRank (damping 0.85; 24 iterations)
Independent Dimension Scoring (scoring-v1)
Decision-Local Rationale Resolution (rationale-rules-v1)
Rationale Overlay Contract Validation (schema 1)
Canonical Content-Addressed Publication
Stable Bounded Projection
Cited Report Composition
```

Where one step covers several analysis algorithms, join their exact names with ` · ` in `method`; do not create extra flow steps or change endpoint order. Use `Write Authorization Gate` for an authorized mutation, `Deterministic Result Handoff` for delivery, and describe engineering review or agent-assisted interpretation only as activity after that handoff. Do not call governance or external interpretation an algorithm.

- [ ] **Step 5: Render step provenance and method in the details panel**

Add two rows between the route and description:

```html
<dl class="panel-classification">
  <div><dt>Provenance</dt><dd id="panelProvenance">—</dd></div>
  <div><dt>Algorithm / control</dt><dd id="panelMethod">—</dd></div>
</dl>
```

Bind `panelProvenance` and `panelMethod` with the other DOM references. In `applyStep()`, assign `step.provenance` and `step.method` with `textContent`. Include both values in the polite step announcement so keyboard and screen-reader users receive the same classification.

- [ ] **Step 6: Expose the analysis and graph algorithm sequence in node copy**

Keep node dimensions unchanged. Update compact node metadata so:

- analysis identifies `TF-IDF · SVO · decisions` and `rule-based` processing;
- graph identifies `typed edges · PageRank` and `scoring-v1`;
- overlay identifies `rationale-rules-v1` and `rank_eligible: false`;
- presentation identifies bounded deterministic projection and citations;
- caller identifies `human + optional external LLM`.

The full names remain in step methods and the README; node text stays short enough to preserve the approved geometry.

- [ ] **Step 7: Run diagram and full repository validation**

Run:

```bash
UV_CACHE_DIR=/private/tmp/architecture-graph-uv-cache uv run pytest \
  tests/test_architecture_documentation.py -q
perl -0777 -ne 'print $1 if m{<script>(.*)</script>}s' \
  architecture.html > /private/tmp/architecture-inline.js
node --check /private/tmp/architecture-inline.js
git diff --check
UV_CACHE_DIR=/private/tmp/architecture-graph-uv-cache uv run pytest -q
```

Expected: all documentation tests pass; inline JavaScript parses; the complete suite passes with at least the prior 350 tests plus the new documentation tests.

Run the existing deterministic geometry/accessibility checks from `.superpowers/sdd/final-fix-report.md` if that report is available. Otherwise verify from source that the stage retains the 934px narrow-screen minimum, all nine node positions remain unchanged, node button semantics remain present, the details announcement remains polite and atomic, and reduced-motion rules remain intact.

If a render-capable browser is available, open `architecture.html` and inspect:

- default Index corpus flow at desktop width;
- Build graph with the PageRank step active;
- Build rationale with contract validation active;
- Compose report at its final caller handoff;
- horizontal stage scrolling at 375px viewport width;
- dark and light themes.

Record an unavailable browser as a validation limitation, not as a passed rendered check.

- [ ] **Step 8: Commit the provenance-aware diagram**

```bash
git add architecture.html tests/test_architecture_documentation.py
git commit -m "docs: label diagram algorithms and provenance"
```

---

## Completion review

After both tasks:

1. Compare the README algorithm registry with every method label in `architecture.html`.
2. Confirm that only the caller can display `Optional external LLM` or `Human/control` node provenance.
3. Confirm that no base or overlay processing step carries an LLM provenance label.
4. Confirm that authorization and engineering review appear as controls, not algorithms.
5. Run `git status --short`, `git diff --check`, the documentation test module, inline JavaScript parsing, and the full pytest suite.
6. Request a whole-branch review before integration.
