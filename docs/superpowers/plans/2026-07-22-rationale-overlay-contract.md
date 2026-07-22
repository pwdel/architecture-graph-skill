# Rationale Overlay Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic rationale interpretation as a separately published, non-ranking overlay while preserving every v0.3.1 semantic-schema-v2 decision, edge, ranking, score, and base snapshot identity.

**Architecture:** Define and enforce the overlay record and manifest contracts before implementing rationale discovery. Build overlays from immutable base decisions and evidence, publish them in a separate atomic namespace, and compose them only at the query/report presentation boundary. The base catalog, graph builder, and `scoring-v1` pipeline remain unchanged.

**Tech Stack:** Python 3.12, standard library, existing canonical JSON/JSONL and snapshot utilities, PyYAML, pytest; no network, model downloads, embeddings, provider SDKs, or runtime LLM.

## Global Constraints

- Keep semantic-schema-v2 `decisions.jsonl`, `rankings.jsonl`, and `edges.jsonl` byte-identical for the same corpus and configuration.
- Keep the base snapshot ID and ranking digest unchanged.
- Do not modify `scoring-v1`, rank feature inputs, PageRank eligibility, or ranking order.
- Store rationale interpretation in a separate overlay namespace bound to one exact base snapshot.
- Require `rank_eligible` to be exactly `false` on every rationale resolution.
- Reject overlay node or edge records that could enter ranking.
- Preserve exact `get decisions` behavior as base-only.
- Compose compatible overlays by default only in `decisions`, `explain`, and `report`; support `--base-only` on those commands.
- Treat `explicit`, `recognized_alias`, `ambiguous`, and `missing` as valid deterministic results.
- Never synthesize rationale text or invoke an LLM.
- Run each behavior change test-first and commit only after focused and cumulative tests pass.

## File Map

- `scripts/architecture_graph/overlay_types.py`: immutable overlay values, manifest, coverage, and resolution result contracts.
- `scripts/architecture_graph/overlay_contract.py`: rationale record, reference, digest, canonical-order, and non-ranking validation.
- `scripts/architecture_graph/overlay_snapshot.py`: separate overlay paths, readers, atomic staging, and current pointer publication.
- `scripts/architecture_graph/rationale_rules.py`: versioned alias and scope-rule loading.
- `scripts/architecture_graph/rationale_resolver.py`: deterministic candidate discovery and one-resolution-per-decision reduction.
- `scripts/architecture_graph/overlay_queries.py`: base-plus-overlay composition and overlay status/find queries.
- `scripts/architecture_graph/resources/rationale-rules-v1.json`: exact roles, aliases, precedence, and scoped `why_now` behavior.
- `scripts/architecture_graph/cli.py`: `rationale build/status/find` and `--base-only` command surface.
- `scripts/architecture_graph/semantic_queries.py`: optional overlay composition for decisions and explain.
- `scripts/architecture_graph/report.py`: resolved rationale presentation without modifying base assertions.
- `scripts/architecture_graph/capabilities.py`: additive rationale-overlay capabilities.
- `scripts/architecture_graph/fingerprint.py`: rationale rule digest outside the frozen base pipeline digest.
- `tests/helpers/rationale_overlay.py`: valid base/overlay factories and byte-capture helpers.
- `tests/test_overlay_contract.py`: schema, reference, digest, and immutability validation.
- `tests/test_overlay_snapshot.py`: atomic separate publication and compatibility behavior.
- `tests/test_rationale_resolver.py`: alias, scope, ambiguity, and missing-resolution tests.
- `tests/test_overlay_queries.py`: composition, base-only, and bounded query tests.
- `tests/test_rationale_cli.py`: command and error-envelope acceptance tests.
- `tests/test_rationale_regression.py`: frozen v0.3.1 and 764-segment design-plan-shaped acceptance tests.

---

### Task 1: Freeze the v0.3.1 Base Contract

**Files:**
- Create: `tests/helpers/rationale_overlay.py`
- Create: `tests/test_overlay_contract.py`
- Modify: `tests/test_phase2_golden.py`
- Modify: `tests/test_ranking.py`

**Interfaces:**
- Produces `BaseArtifactCapture(snapshot_id: str, ranking_digest: str, files: Mapping[str, bytes])`.
- Produces `capture_frozen_base(reader: SnapshotReader) -> BaseArtifactCapture`.
- Defines immutable golden expectations for semantic schema 2 and `scoring-v1`.

- [ ] **Step 1: Write failing base-artifact immutability tests**

```python
def test_repeated_index_preserves_frozen_base(phase2_repository):
    first = index_fixture(phase2_repository)
    before = capture_frozen_base(first.reader)
    second = index_fixture(phase2_repository)
    after = capture_frozen_base(second.reader)
    assert after == before

def test_frozen_scoring_contract_remains_v1(indexed_phase2_repo):
    capture = capture_frozen_base(indexed_phase2_repo.reader)
    assert capture.semantic_schema == 2
    assert capture.scoring_rule_version == "scoring-v1"
```

Run: `uv run pytest tests/test_overlay_contract.py tests/test_phase2_golden.py tests/test_ranking.py -q`  
Expected: FAIL because the capture and overlay contracts do not exist.

- [ ] **Step 2: Implement byte-level base capture helpers**

Read the published manifest plus raw `decisions.jsonl`, `rankings.jsonl`, and `edges.jsonl` bytes. Derive `ranking_digest` from the exact rankings file bytes using the existing canonical SHA-256 helper. Do not reconstruct records before comparison.

- [ ] **Step 3: Lock the existing base golden behavior**

Assert the existing mixed Phase 2 corpus publishes semantic schema 2, `scoring-v1`, the known score set, and byte-identical repeated results. These tests become mandatory compatibility gates for every later task.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_overlay_contract.py tests/test_phase2_golden.py tests/test_ranking.py -q`  
Expected: PASS.

```bash
git add tests/helpers/rationale_overlay.py tests/test_overlay_contract.py tests/test_phase2_golden.py tests/test_ranking.py
git commit -m "test: freeze the v0.3.1 ranking baseline"
```

### Task 2: Define and Enforce the Overlay Contract

**Files:**
- Create: `scripts/architecture_graph/overlay_types.py`
- Create: `scripts/architecture_graph/overlay_contract.py`
- Create: `scripts/architecture_graph/resources/rationale-rules-v1.json`
- Modify: `scripts/architecture_graph/resources/__init__.py`
- Modify: `pyproject.toml`
- Modify: `tests/helpers/rationale_overlay.py`
- Modify: `tests/test_overlay_contract.py`

**Interfaces:**
- Produces frozen `RationaleResolution`, `RationaleCoverage`, `RationaleOverlayManifest`, and `RationaleOverlayResult` dataclasses.
- Produces `validate_rationale_resolution(record: Mapping[str, object], base: SnapshotReader) -> tuple[ValidationIssue, ...]`.
- Produces `validate_rationale_overlay(manifest: Mapping[str, object], records: Sequence[Record], base: SnapshotReader) -> tuple[ValidationIssue, ...]`.
- Produces `load_rationale_rules(version: str = "rationale-rules-v1") -> Mapping[str, object]`.

- [ ] **Step 1: Write failing shape and reference tests**

```python
def test_valid_resolution_is_bound_to_exact_decision(valid_resolution, base_reader):
    assert validate_rationale_resolution(valid_resolution, base_reader) == ()

@pytest.mark.parametrize("change", [
    {"rank_eligible": True},
    {"normalized_role": "context"},
    {"classification": "guessed"},
    {"decision_content_digest": "sha256:" + "0" * 64},
    {"evidence_ids": ["evidence:missing"]},
])
def test_invalid_resolution_is_rejected(valid_resolution, base_reader, change):
    candidate = {**valid_resolution, **change}
    assert validate_rationale_resolution(candidate, base_reader)
```

Run: `uv run pytest tests/test_overlay_contract.py -q`  
Expected: FAIL because overlay types and validators do not exist.

- [ ] **Step 2: Implement immutable overlay values and versioned rules**

Define exact enums and tuple-backed collections. Store aliases as explicit records with `observed_role`, `classification`, eligible structured locations, eligible section roles, and precedence. Set document-level `why_now` to ineligible and decision-local `why_now` to eligible only through an exact scoped rule.

- [ ] **Step 3: Implement complete contract validation**

Validate ID prefixes, schema version 1, exact base snapshot identity, exact decision digest, evidence and derivation references, canonical unique arrays, allowed classifications, supported rule version/digest, `rank_eligible is False`, and absence of rank-eligible node/edge kinds. Validate exactly one resolution for every base decision.

- [ ] **Step 4: Prove ranking isolation**

Add a test passing every valid overlay record to the rank-input selector and assert that none are accepted. Add explicit rejection tests for `edge`, `ranking`, or base semantic record kinds in an overlay bundle.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_overlay_contract.py tests/test_ranking.py tests/test_phase2_golden.py -q`  
Expected: PASS.

```bash
git add pyproject.toml scripts/architecture_graph/overlay_types.py scripts/architecture_graph/overlay_contract.py scripts/architecture_graph/resources tests/helpers/rationale_overlay.py tests/test_overlay_contract.py tests/test_ranking.py
git commit -m "feat: define non-ranking rationale overlay contracts"
```

### Task 3: Publish Overlays in a Separate Atomic Namespace

**Files:**
- Create: `scripts/architecture_graph/overlay_snapshot.py`
- Create: `tests/test_overlay_snapshot.py`
- Modify: `scripts/architecture_graph/project.py`
- Modify: `scripts/architecture_graph/jsonl_store.py`
- Modify: `tests/helpers/rationale_overlay.py`

**Interfaces:**
- Produces `RationaleOverlayPaths.for_base(project: ProjectPaths, base_snapshot_id: str) -> RationaleOverlayPaths`.
- Produces `publish_rationale_overlay(paths: RationaleOverlayPaths, manifest: RationaleOverlayManifest, result: RationaleOverlayResult) -> str`.
- Produces `RationaleOverlayReader.open(paths: RationaleOverlayPaths, overlay_id: str | None = None) -> RationaleOverlayReader`.
- Reader exposes `manifest`, `iter_resolutions()`, `iter_derivations()`, and `iter_warnings()`.

- [ ] **Step 1: Write failing separate-publication tests**

```python
def test_overlay_publication_never_writes_base_snapshot(base_project, valid_overlay):
    before = capture_frozen_base(valid_overlay.base_reader)
    overlay_id = publish_rationale_overlay(valid_overlay.paths, valid_overlay.manifest, valid_overlay.result)
    after = capture_frozen_base(valid_overlay.base_reader)
    assert after == before
    assert valid_overlay.paths.snapshot(overlay_id).is_dir()

def test_stale_base_aborts_before_pointer_change(base_project, valid_overlay):
    prior = valid_overlay.paths.current_path.read_bytes() if valid_overlay.paths.current_path.exists() else None
    mutate_base_manifest_for_test(valid_overlay.base_reader)
    with pytest.raises(OverlayCompatibilityError, match="base snapshot changed"):
        publish_rationale_overlay(valid_overlay.paths, valid_overlay.manifest, valid_overlay.result)
    assert read_optional(valid_overlay.paths.current_path) == prior
```

Run: `uv run pytest tests/test_overlay_snapshot.py -q`  
Expected: FAIL because separate overlay storage does not exist.

- [ ] **Step 2: Implement overlay paths and immutable reader**

Keep overlay paths below `overlays/rationale/`, never below base `snapshots/`. Resolve `CURRENT` only after verifying its target manifest, base snapshot ID, base ranking digest, and overlay content digest.

- [ ] **Step 3: Implement atomic publication**

Validate before staging, write canonical manifest and JSONL into a unique staging directory, fsync through existing store helpers, revalidate the base snapshot, rename staging atomically, then advance `CURRENT`. Preserve an existing valid overlay if any step fails.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_overlay_snapshot.py tests/test_snapshot.py tests/test_jsonl_store.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/overlay_snapshot.py scripts/architecture_graph/project.py scripts/architecture_graph/jsonl_store.py tests/helpers/rationale_overlay.py tests/test_overlay_snapshot.py
git commit -m "feat: publish immutable rationale overlays"
```

### Task 4: Resolve Rationale Deterministically

**Files:**
- Create: `scripts/architecture_graph/rationale_rules.py`
- Create: `scripts/architecture_graph/rationale_resolver.py`
- Create: `tests/test_rationale_resolver.py`
- Modify: `scripts/architecture_graph/overlay_types.py`
- Modify: `scripts/architecture_graph/resources/rationale-rules-v1.json`

**Interfaces:**
- Produces `RationaleCandidate(decision_id, observed_role, classification, evidence_ids, precedence, scope_kind)`.
- Produces `discover_rationale_candidates(base: SnapshotReader, rules: RationaleRules) -> tuple[RationaleCandidate, ...]`.
- Produces `resolve_rationales(base: SnapshotReader, rules: RationaleRules) -> RationaleOverlayResult`.

- [ ] **Step 1: Write failing alias and scope tests**

```python
@pytest.mark.parametrize("role, classification", [
    ("rationale", "explicit"),
    ("context", "recognized_alias"),
    ("reason", "recognized_alias"),
    ("reasons", "recognized_alias"),
    ("justification", "recognized_alias"),
    ("why", "recognized_alias"),
])
def test_decision_local_roles_resolve(role, classification, structured_decision):
    result = resolve_rationales(structured_decision(role), load_rationale_rules())
    assert result.resolutions[0].classification == classification

def test_document_why_now_is_not_attached_to_decisions(plan_with_top_level_why_now):
    result = resolve_rationales(plan_with_top_level_why_now, load_rationale_rules())
    assert result.resolutions[0].classification == "missing"
```

Run: `uv run pytest tests/test_rationale_resolver.py -q`  
Expected: FAIL because no rationale resolver exists.

- [ ] **Step 2: Discover bounded structured and prose candidates**

For JSON/YAML, group scalar evidence by the exact decision parent already used by the decision candidate contract. For prose/ADRs, use explicit decision identity and bounded heading sections. Preserve original role, exact evidence, source path/span, and scope kind. Do not use lexical similarity or broad co-occurrence.

- [ ] **Step 3: Reduce one resolution per decision**

Apply rule precedence. Aggregate candidates only when their decision identity and normalized role match. Mark incompatible eligible passages `ambiguous`; emit `missing` when none exist. Add `missing_rationale` to `resolves_diagnostics` only for explicit or recognized-alias resolutions whose base decision contains that diagnostic.

- [ ] **Step 4: Emit complete coverage and derivations**

Count decisions examined, explicit, recognized aliases, ambiguous, missing, and warnings. Every non-missing resolution retains evidence IDs; every resolution has a deterministic derivation and content-addressed ID.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_rationale_resolver.py tests/test_overlay_contract.py tests/test_decisions.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/rationale_rules.py scripts/architecture_graph/rationale_resolver.py scripts/architecture_graph/overlay_types.py scripts/architecture_graph/resources/rationale-rules-v1.json tests/test_rationale_resolver.py
git commit -m "feat: resolve source-backed decision rationale"
```

### Task 5: Compose Overlays into Bounded Queries and Reports

**Files:**
- Create: `scripts/architecture_graph/overlay_queries.py`
- Create: `tests/test_overlay_queries.py`
- Modify: `scripts/architecture_graph/views.py`
- Modify: `scripts/architecture_graph/semantic_queries.py`
- Modify: `scripts/architecture_graph/report.py`
- Modify: `scripts/architecture_graph/paging.py`

**Interfaces:**
- Produces `compose_decision_summary(base: Record, resolution: Record | None) -> Record`.
- Produces `rationale_status_query(reader: RationaleOverlayReader, ...) -> QueryEnvelope`.
- Produces `rationale_find_query(reader: RationaleOverlayReader, classification: str | None, ...) -> QueryEnvelope`.
- `decisions_query`, `explain_query`, and `build_report` accept `overlay_reader: RationaleOverlayReader | None` and `base_only: bool = False`.

- [ ] **Step 1: Write failing composition and base-only tests**

```python
def test_composition_resolves_active_diagnostic_without_mutating_base(base_decision, context_resolution):
    original = canonical_bytes(base_decision)
    composed = compose_decision_summary(base_decision, context_resolution)
    assert composed["base_diagnostics"] == ["missing_rationale"]
    assert composed["resolved_diagnostics"] == ["missing_rationale"]
    assert composed["active_diagnostics"] == []
    assert canonical_bytes(base_decision) == original

def test_base_only_reproduces_v031_query_bytes(base_reader, overlay_reader):
    assert render(decisions_query(base_reader, base_only=True)) == frozen_v031_decisions_output(base_reader)
```

Run: `uv run pytest tests/test_overlay_queries.py -q`  
Expected: FAIL because overlay composition does not exist.

- [ ] **Step 2: Implement immutable presentation composition**

Copy compact base summaries, retain `base_diagnostics`, calculate resolved and active diagnostics, and attach a bounded rationale-resolution summary. Never alter the catalog or persist composed records.

- [ ] **Step 3: Add bounded status and find queries**

Fit overlay coverage and compact resolutions within the existing character budget. Bind cursors to base snapshot, overlay ID, command, classification, projection version, fields, and limits. Reject attempts to request unbounded evidence arrays from compact views.

- [ ] **Step 4: Compose reports and explanations**

Reports show “rationale recognized through `context`” with stable evidence references and omit resolved warnings from active review findings. Explanations expose base diagnostics, overlay derivation, alias rule version, and evidence counts. `base_only=True` bypasses all overlay reads.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_overlay_queries.py tests/test_semantic_queries.py tests/test_report.py tests/test_query.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/overlay_queries.py scripts/architecture_graph/views.py scripts/architecture_graph/semantic_queries.py scripts/architecture_graph/report.py scripts/architecture_graph/paging.py tests/test_overlay_queries.py tests/test_semantic_queries.py tests/test_report.py
git commit -m "feat: compose rationale overlays into semantic views"
```

### Task 6: Add Rationale Commands and Compatibility Errors

**Files:**
- Modify: `scripts/architecture_graph/cli.py`
- Modify: `scripts/architecture_graph/errors.py`
- Modify: `scripts/architecture_graph/capabilities.py`
- Create: `tests/test_rationale_cli.py`
- Modify: `tests/test_capabilities.py`
- Modify: `tests/test_cli_smoke.py`

**Interfaces:**
- Adds `architecture-graph rationale build|status|find`.
- Adds `--base-only` to `decisions`, `explain`, and `report`.
- Adds typed errors `overlay_not_found`, `overlay_incompatible`, `overlay_stale`, and `overlay_validation_failed`.

- [ ] **Step 1: Write failing command-surface tests**

```python
def test_rationale_commands_are_advertised():
    capability = capability_record()
    assert "rationale build" in capability["commands"]
    assert "rationale status" in capability["commands"]
    assert "rationale find" in capability["commands"]

def test_rationale_build_and_composed_report(repo, capsys):
    indexed = index_fixture(repo)
    assert main(["rationale", "build", str(repo), "--corpus", indexed.corpus_id, "--json"]) == 0
    assert main(["report", str(repo), "--corpus", indexed.corpus_id]) == 0
    assert "recognized through context" in capsys.readouterr().out
```

Run: `uv run pytest tests/test_rationale_cli.py tests/test_capabilities.py tests/test_cli_smoke.py -q`  
Expected: FAIL because the commands are unavailable.

- [ ] **Step 2: Implement parser and command dispatch**

Require explicit base snapshot selection for `rationale build` unless one unambiguous current base exists. Make status read-only. Make find bounded and cursor-based. Resolve a compatible current overlay automatically for composed commands unless `--base-only` is supplied.

- [ ] **Step 3: Implement typed compatibility failures**

Return structured errors for missing, stale, incompatible, or invalid overlays. A composed command may use base-only fallback only when explicitly requested; it must not silently apply or ignore an incompatible overlay.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_rationale_cli.py tests/test_capabilities.py tests/test_cli_smoke.py tests/test_phase2_cli.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/cli.py scripts/architecture_graph/errors.py scripts/architecture_graph/capabilities.py tests/test_rationale_cli.py tests/test_capabilities.py tests/test_cli_smoke.py tests/test_phase2_cli.py
git commit -m "feat: expose rationale overlay commands"
```

### Task 7: Prove the Real-World Regression and Prepare v0.4.0

**Files:**
- Create: `tests/test_rationale_regression.py`
- Modify: `tests/test_phase2_publication.py`
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `references/agent-usage.md`
- Modify: `scripts/architecture_graph/__init__.py`
- Modify: `scripts/architecture_graph/analysis_types.py`
- Modify: `scripts/architecture_graph/analysis.py`
- Modify: `tests/test_phase2_golden.py`

**Interfaces:**
- Package and skill version become `0.4.0` only after all compatibility and regression tests pass.
- Base semantic schema remains 2 and scoring remains `scoring-v1`.

- [ ] **Step 1: Write the design-plan-shaped regression test**

```python
def test_design_plan_overlay_resolves_context_without_changing_rankings(design_plan_repo):
    base = index_design_plan(design_plan_repo)
    frozen = capture_frozen_base(base.reader)
    overlay = build_rationale_overlay(base.reader)
    publish_rationale_overlay(base.overlay_paths, overlay.manifest, overlay.result)
    assert capture_frozen_base(base.reader) == frozen
    assert len(overlay.result.resolutions) == 7
    assert any(item.classification == "recognized_alias" and "context" in item.observed_roles for item in overlay.result.resolutions)
    report = composed_report(base.reader, base.overlay_paths)
    assert "missing rationale" not in report.active_review_findings
```

Run: `uv run pytest tests/test_rationale_regression.py -q`  
Expected: FAIL until the full overlay path is integrated.

- [ ] **Step 2: Document immutable-base and overlay workflows**

Explain rationale build/status/find, automatic compatible composition, `--base-only`, active versus base diagnostics, stale overlay errors, and the explicit promise that scoring-v1 and semantic-schema-v2 base artifacts remain frozen.

- [ ] **Step 3: Bump only package/tool identity**

Set runtime version defaults to `0.4.0`. Do not change the base semantic schema or scoring rule version. Refresh the editable package metadata with `uv sync --reinstall-package architecture-graph-skill`.

- [ ] **Step 4: Run complete verification**

Run: `uv sync --frozen`  
Expected: success.

Run: `uv run pytest -q`  
Expected: all tests PASS.

Run: `uv build`  
Expected: wheel and source distribution build successfully.

Run: `uv run architecture-graph --version`  
Expected: `0.4.0`.

Run: `uv run architecture-graph capabilities --json`  
Expected: valid JSON advertising rationale overlays while still reporting `scoring-v1`.

Run: `git diff --check`  
Expected: no output.

- [ ] **Step 5: Commit release readiness**

```bash
git add README.md SKILL.md references/agent-usage.md scripts/architecture_graph tests/test_rationale_regression.py tests/test_phase2_publication.py tests/test_phase2_golden.py
git commit -m "chore: prepare architecture graph 0.4.0"
```

- [ ] **Step 6: Request final code review**

Review the complete branch against `docs/superpowers/specs/2026-07-22-rationale-overlay-contract-design.md`, with special attention to byte-level base immutability, rank-input isolation, stale-base publication races, composed diagnostic semantics, cursor bindings, and v0.3.1 compatibility. Resolve every critical or important finding and repeat focused plus full verification.
