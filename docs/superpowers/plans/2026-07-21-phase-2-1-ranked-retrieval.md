# Phase 2.1 Ranked Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make full-corpus semantic analysis reliably usable through compact deterministic rankings, format-neutral decision reduction, explainable measures, and a concise report with paginated evidence.

**Architecture:** Keep complete semantic records in immutable snapshots, then project them into bounded command-specific summaries at the query boundary. Add normalized structured-object decision candidates before the existing reducer, extend independent score vectors, and render reports from compact assertions whose complete provenance remains addressable through `evidence` and `explain`.

**Tech Stack:** Python 3.12, standard library sparse statistics and graph algorithms, PyYAML, jsonlines, jmespath, pytest; no network, model download, embeddings, vector database, provider SDK, or runtime LLM.

## Global Constraints

- Analyze every eligible source, segment, term, phrase, claim, node, and edge in the selected corpus.
- Apply `limit` and `max_chars` only to response presentation; they must not change persisted scores, ordering, or identities.
- Keep complete evidence and derivation references in snapshots while returning bounded summary projections from list commands.
- Every successful cursor advances; never represent an oversized record as a successful empty page.
- Treat Markdown, prose, ADRs, JSON, YAML, Mermaid, and PlantUML through one normalized decision-candidate contract.
- Keep extraction confidence, corroboration, authority/lifecycle, completeness, criticality, review priority, and navigation rank independent and explainable.
- Count duplicate source bytes once for frequency, corroboration, and ranking.
- Keep the default report under a hard output ceiling and show at most two representative citations per assertion.
- Return explicit coverage diagnostics for empty or degraded semantic stages.
- Keep analysis deterministic and offline; do not add dependencies or network access.
- Run every behavior change test-first and commit only after focused and cumulative tests pass.

## File Map

- `scripts/architecture_graph/views.py`: compact record summaries and bounded representative-reference selection.
- `scripts/architecture_graph/paging.py`: progress-safe response fitting and typed oversized-record failure.
- `scripts/architecture_graph/terms.py`: complete corpus counts and deterministic lexical feature records.
- `scripts/architecture_graph/ranking.py`: graph/lexical features and independent decision measures.
- `scripts/architecture_graph/decision_candidates.py`: normalized prose and structured-object decision candidates.
- `scripts/architecture_graph/decisions.py`: candidate reduction, lifecycle, completeness, and diagnostics.
- `scripts/architecture_graph/semantic_queries.py`: ranked summary queries, detail, evidence, and explanation projections.
- `scripts/architecture_graph/report.py`: adaptive concise report and appendix references.
- `scripts/architecture_graph/analysis.py`: candidate-stage integration and coverage records.
- `scripts/architecture_graph/cli.py`: error mapping, report ceiling, and valid capabilities output.
- `scripts/architecture_graph/resources/{decision-rules-v1,scoring-v1}.json`: versioned roles, feature weights, and formulas.
- `tests/fixtures/phase2_large_plan/`: regression corpus shaped like the observed 764-segment design plan.

---

### Task 1: Compact Semantic Views and Progress-Safe Pagination

**Files:**
- Create: `scripts/architecture_graph/views.py`
- Modify: `scripts/architecture_graph/paging.py`
- Modify: `scripts/architecture_graph/errors.py`
- Modify: `scripts/architecture_graph/semantic_queries.py`
- Test: `tests/test_semantic_queries.py`
- Test: `tests/test_query.py`

**Interfaces:**
- Produces `summarize_record(record: Record, rankings: Mapping[str, Record] | None = None, evidence_limit: int = 2) -> Record`.
- Produces `RecordTooLargeError(record_id: str, max_chars: int, minimum_chars: int)` with code `record_too_large`.
- `terms_query`, `decisions_query`, and `neighbors_query` page compact summaries; `get` remains the complete-record path.

- [ ] **Step 1: Write failing summary and oversized-page tests**

```python
def test_term_query_summarizes_unbounded_evidence(semantic_reader):
    term = semantic_reader.mutable_record("terms", 0)
    term["evidence_ids"] = [f"evidence:{n:04d}" for n in range(2_000)]
    page = terms_query(semantic_reader, limit=1, max_chars=1_200)
    assert len(page.items) == 1
    assert page.items[0]["evidence_count"] == 2_000
    assert len(page.items[0]["top_evidence_ids"]) <= 2
    assert "evidence_ids" not in page.items[0]

def test_paging_never_returns_a_nonprogressing_empty_page():
    with pytest.raises(RecordTooLargeError) as raised:
        page_records([{"id": "term:x", "text": "x" * 5_000}], binding={}, fields=None, limit=1, max_chars=100)
    assert raised.value.record_id == "term:x"
```

Run: `uv run pytest tests/test_semantic_queries.py tests/test_query.py -q`  
Expected: FAIL because semantic commands expose full records and pagination can return a cursor at its original offset.

- [ ] **Step 2: Implement command-specific summary projection**

Create summaries containing stable identity, labels, bounded top evidence IDs, evidence/derivation counts, relevant score components, and record-specific scalar fields. Exclude unbounded arrays and nested complete records. Select representative evidence IDs by distinct source-content hash, authority, extraction confidence, then canonical source order.

- [ ] **Step 3: Make page fitting progress-safe**

Fit projected records only. If shrinking removes every item while records remain, serialize the first compact item alone to calculate `minimum_chars` and raise `RecordTooLargeError`. Bind projection version into cursors and assert every returned cursor offset is greater than the input offset.

- [ ] **Step 4: Run focused and cumulative tests**

Run: `uv run pytest tests/test_query.py tests/test_semantic_queries.py tests/test_phase2_cli.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/architecture_graph/views.py scripts/architecture_graph/paging.py scripts/architecture_graph/errors.py scripts/architecture_graph/semantic_queries.py tests/test_query.py tests/test_semantic_queries.py tests/test_phase2_cli.py
git commit -m "fix: return compact progress-safe semantic pages"
```

### Task 2: Complete Deterministic Term Features and Ranking

**Files:**
- Modify: `scripts/architecture_graph/terms.py`
- Modify: `scripts/architecture_graph/ranking.py`
- Modify: `scripts/architecture_graph/resources/scoring-v1.json`
- Test: `tests/test_terms.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Term records add `occurrence_count`, `phrase_frequency`, and `lexical_features` without capping complete evidence IDs.
- Ranking records expose independent `lexical_salience` and `graph_centrality` components plus versioned navigation features.
- Produces deterministic bounded PageRank over typed semantic edges.

- [ ] **Step 1: Write failing full-corpus and ordering tests**

```python
def test_term_analysis_is_independent_of_query_page_size(parsed_large_corpus):
    terms = discover_terms(parsed_large_corpus).terms
    assert sum(t["occurrence_count"] for t in terms) == parsed_large_corpus.eligible_token_count
    assert all("lexical_features" in term for term in terms)

def test_rank_order_is_stable_across_query_limits(snapshot_reader):
    first = collect_pages(snapshot_reader, command="terms", limit=1)
    seventh = collect_pages(snapshot_reader, command="terms", limit=7)
    assert [x["id"] for x in first] == [x["id"] for x in seventh]
```

Run: `uv run pytest tests/test_terms.py tests/test_ranking.py -q`  
Expected: FAIL because the additional full-corpus features and PageRank are absent.

- [ ] **Step 2: Materialize lexical features over all distinct content**

Count occurrences across every eligible sentence while deduplicating identical source-content hashes. Store TF-IDF, document frequency, phrase frequency, glossary/heading/acronym/diagram signals, and total occurrences. Do not truncate evidence during analysis.

- [ ] **Step 3: Add deterministic graph centrality**

Implement fixed-iteration PageRank with canonical node order, damping and iteration count from `scoring-v1.json`, typed edge eligibility, finite clamped output, and canonical rounding. Persist lexical and graph components independently; combine them only through the documented navigation formula.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_terms.py tests/test_ranking.py tests/test_phase2_golden.py -q`  
Expected: PASS with intentional golden updates.

```bash
git add scripts/architecture_graph/terms.py scripts/architecture_graph/ranking.py scripts/architecture_graph/resources/scoring-v1.json tests/test_terms.py tests/test_ranking.py tests/fixtures/golden
git commit -m "feat: rank the complete architecture corpus"
```

### Task 3: Format-Neutral Decision Candidate Reconstruction

**Files:**
- Create: `scripts/architecture_graph/decision_candidates.py`
- Modify: `scripts/architecture_graph/analysis_types.py`
- Modify: `scripts/architecture_graph/decisions.py`
- Modify: `scripts/architecture_graph/analysis.py`
- Modify: `scripts/architecture_graph/resources/decision-rules-v1.json`
- Test: `tests/test_decisions.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces frozen `DecisionCandidate` with `candidate_id`, `anchor_kind`, `field_roles`, `scope`, `status`, `evidence_ids`, `derivation_ids`, and parser provenance.
- Produces `collect_decision_candidates(parsed: ParsedCorpus, catalog: RecordCatalog) -> DecisionCandidateResult`.
- Changes `reduce_decisions(catalog, graph, candidates) -> DecisionResult`.

- [ ] **Step 1: Write failing cross-format reconstruction tests**

```python
@pytest.mark.parametrize("fixture", ["decision.md", "decision.yaml", "decision.json", "ADR-001.md"])
def test_equivalent_formats_produce_decision_candidates(fixture, parsed_fixture):
    result = collect_decision_candidates(parsed_fixture, parsed_fixture.catalog)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.field_roles["decision"] == "Frontend requests must use the API adapter."
    assert candidate.status == "accepted"

def test_json_sibling_fields_reduce_to_one_decision(parsed_decision_log):
    candidates = collect_decision_candidates(parsed_decision_log, parsed_decision_log.catalog)
    assert len(candidates.candidates) == 7
```

Run: `uv run pytest tests/test_decisions.py tests/test_analysis.py -q`  
Expected: FAIL because decisions currently require previously extracted claims under a decision heading.

- [ ] **Step 2: Group normalized candidate evidence**

Map prose sections, ADR metadata, JSON-pointer parents, YAML mapping parents, and explicitly labeled diagram scopes into the same field roles. Use grouping anchors in this order: explicit decision ID, structured parent, decision heading scope, normalized title plus compatible scope/lifecycle. Emit diagnostics instead of merging ambiguous candidates.

- [ ] **Step 3: Reduce candidates conservatively**

Build decisions from explicit candidate text and attach matching claims when present. Normalize lifecycle status through versioned rules. Preserve rationale and consequence evidence separately, mark absent fields in `diagnostic_codes`, and never synthesize missing text.

- [ ] **Step 4: Integrate, verify, and commit**

Run: `uv run pytest tests/test_decisions.py tests/test_analysis.py tests/test_other_ingest.py tests/test_markdown_ingest.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/decision_candidates.py scripts/architecture_graph/analysis_types.py scripts/architecture_graph/decisions.py scripts/architecture_graph/analysis.py scripts/architecture_graph/resources/decision-rules-v1.json tests/test_decisions.py tests/test_analysis.py
git commit -m "feat: reconstruct decisions across document formats"
```

### Task 4: Explainable Independent Decision Measures

**Files:**
- Modify: `scripts/architecture_graph/ranking.py`
- Modify: `scripts/architecture_graph/schemas.py`
- Modify: `scripts/architecture_graph/resources/scoring-v1.json`
- Modify: `scripts/architecture_graph/semantic_queries.py`
- Test: `tests/test_ranking.py`
- Test: `tests/test_semantic_queries.py`

**Interfaces:**
- Decision ranking entries expose `extraction_confidence`, `corroboration`, `completeness`, `criticality`, `review_priority`, and `navigation`; authority/lifecycle remains categorical.
- `explain_query` returns compact feature inputs, formula/rule versions, score outputs, and bounded evidence/derivation summaries.

- [ ] **Step 1: Write failing score-independence tests**

```python
def test_well_parsed_trivial_decision_is_not_automatically_critical(decision_graph):
    ranking = rank_decision(decision_graph.trivial_structured_decision)
    assert ranking["scores"]["extraction_confidence"]["score"] > .8
    assert ranking["scores"]["criticality"]["score"] < .5

def test_high_impact_weakly_parsed_decision_has_high_review_priority(decision_graph):
    ranking = rank_decision(decision_graph.weak_atomicity_decision)
    assert ranking["scores"]["criticality"]["score"] > .7
    assert ranking["scores"]["review_priority"]["score"] > .7
```

Run: `uv run pytest tests/test_ranking.py tests/test_semantic_queries.py -q`  
Expected: FAIL because current ranking averages two generic features per score.

- [ ] **Step 2: Implement versioned independent feature vectors**

Calculate extraction from anchor strength and field recognition; corroboration from distinct agreeing content hashes; completeness from explicit role presence; criticality from scope, boundary impact, required modality, security/data-integrity signals, and reversibility; review priority from contradictions, lifecycle conflicts, missing rationale/scope, low extraction, and uncorroborated high impact. Keep authority and lifecycle as returned categorical metadata.

- [ ] **Step 3: Make explanations compact and complete**

Return feature names, normalized inputs, formula version, final score, evidence count, representative evidence, and derivation references without nesting the complete underlying record. Full records remain reachable through `get`.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_ranking.py tests/test_semantic_queries.py tests/test_schemas.py -q`  
Expected: PASS (omit `tests/test_schemas.py` if no standalone file exists and cover through `test_analysis_types.py`).

```bash
git add scripts/architecture_graph/ranking.py scripts/architecture_graph/schemas.py scripts/architecture_graph/resources/scoring-v1.json scripts/architecture_graph/semantic_queries.py tests/test_ranking.py tests/test_semantic_queries.py tests/test_analysis_types.py
git commit -m "feat: explain independent decision measures"
```

### Task 5: Concise Report and Evidence Appendix

**Files:**
- Modify: `scripts/architecture_graph/report.py`
- Modify: `scripts/architecture_graph/semantic_queries.py`
- Modify: `scripts/architecture_graph/cli.py`
- Test: `tests/test_report.py`
- Test: `tests/test_phase2_cli.py`

**Interfaces:**
- `ReportLimits` adds `max_chars`, `citation_limit=2`, and deterministic per-section minimum/maximum values.
- Report assertions contain `evidence_count`, `shown_evidence_ids`, and `appendix_record_id`.
- `evidence_query` accepts report assertion IDs and pages their complete evidence ledger.

- [ ] **Step 1: Write failing bounded-report tests**

```python
def test_report_caps_inline_citations_and_points_to_appendix(large_reader):
    result = build_report(large_reader, limits=ReportLimits(max_chars=12_000))
    text = render_report_text(result)
    assert len(text) <= 12_000
    assert all(len(a["citations"]) <= 2 for a in result.assertions)
    assert any(a["evidence_count"] > len(a["citations"]) for a in result.assertions)
    assert all(a["appendix_record_id"] for a in result.assertions)
```

Run: `uv run pytest tests/test_report.py tests/test_phase2_cli.py -q`  
Expected: FAIL because reports hydrate all citations and ignore `--max-chars`.

- [ ] **Step 2: Build adaptive deterministic sections**

Select accepted/proposed decisions, navigation hubs, critical constraints, review gaps, contradictions, and glossary terms by their independent rankings. Guarantee section minimums when records exist, enforce section maximums, and shrink lowest-priority assertions until the rendered report fits the hard ceiling.

- [ ] **Step 3: Publish assertion-ledger appendix references**

Give every assertion a stable ID derived from snapshot, section, subject record, and ranking version. Retain complete evidence IDs in the report result/ledger but serialize only counts and representative citations. Resolve assertion IDs through the existing `evidence` command.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest tests/test_report.py tests/test_phase2_cli.py tests/test_phase2_golden.py -q`  
Expected: PASS with bounded golden output.

```bash
git add scripts/architecture_graph/report.py scripts/architecture_graph/semantic_queries.py scripts/architecture_graph/cli.py tests/test_report.py tests/test_phase2_cli.py tests/fixtures/golden
git commit -m "feat: separate concise reports from evidence appendices"
```

### Task 6: Coverage Diagnostics and Real-World Acceptance

**Files:**
- Modify: `scripts/architecture_graph/analysis.py`
- Modify: `scripts/architecture_graph/capabilities.py`
- Modify: `scripts/architecture_graph/cli.py`
- Modify: `references/agent-usage.md`
- Modify: `README.md`
- Create: `tests/fixtures/phase2_large_plan/design-plan.json`
- Test: `tests/test_phase2_publication.py`
- Test: `tests/test_phase2_cli.py`
- Test: `tests/test_phase2_golden.py`

**Interfaces:**
- Semantic envelopes/report JSON include `coverage` with selected/parsed sources, eligible segments, candidates, reduced records, warnings, degraded adapters, and rule versions.
- Successful `capabilities --json` always writes one valid JSON value; serialization failure exits nonzero.

- [ ] **Step 1: Write failing diagnostics and end-to-end acceptance tests**

```python
def test_large_plan_stays_graph_native(indexed_large_plan, capsys):
    terms = run_json("terms", indexed_large_plan, "--limit", "20", "--max-chars", "12000")
    decisions = run_json("decisions", indexed_large_plan, "--limit", "20")
    report = run_text("report", indexed_large_plan, "--max-chars", "12000")
    assert terms["items"]
    assert len(decisions["items"]) == 7
    assert len(report) <= 12_000
    assert terms["coverage"]["eligible_segments"] >= 700

def test_zero_reduced_decisions_explains_candidate_failures(indexed_ambiguous_corpus):
    result = run_json("decisions", indexed_ambiguous_corpus)
    assert result["items"] == []
    assert result["coverage"]["decision_candidates"] > 0
    assert result["diagnostics"]
```

Run: `uv run pytest tests/test_phase2_publication.py tests/test_phase2_cli.py tests/test_phase2_golden.py -q`  
Expected: FAIL because coverage is not returned and the large-plan regression fixture is absent.

- [ ] **Step 2: Persist and expose coverage records**

Record per-stage input, candidate, output, warning, degradation, and version counts during analysis. Attach bounded coverage metadata to semantic query envelopes and report JSON. Treat silent capability serialization as an error path.

- [ ] **Step 3: Add the regression corpus and agent guidance**

Create a compact generated fixture with more than 700 structured segments, seven decision objects, repeated glossary terms, and large evidence fan-out. Document that ranking always covers the complete corpus while query budgets only bound presentation, and show the report/evidence follow-up workflow.

- [ ] **Step 4: Run complete verification**

Run: `uv run pytest -q`  
Expected: all tests PASS.

Run: `uv run architecture-graph capabilities --json`  
Expected: one nonempty valid JSON record.

Run: index the large fixture, then execute `terms`, `decisions`, `report`, `evidence`, and `explain` with a 12,000-character ceiling.  
Expected: nonempty ranked terms, seven decisions, bounded report, progressing evidence pages, and explainable scores.

- [ ] **Step 5: Commit**

```bash
git add scripts/architecture_graph/analysis.py scripts/architecture_graph/capabilities.py scripts/architecture_graph/cli.py references/agent-usage.md README.md tests/fixtures/phase2_large_plan tests/test_phase2_publication.py tests/test_phase2_cli.py tests/test_phase2_golden.py
git commit -m "test: prove ranked retrieval on a large design plan"
```

### Task 7: Release Readiness and Pull Request

**Files:**
- Modify: `pyproject.toml`
- Modify: `scripts/architecture_graph/__init__.py`
- Modify: `SKILL.md`
- Modify: `uv.lock`

**Interfaces:**
- Package and skill version become `0.3.1` only after all implementation tests pass.

- [ ] **Step 1: Update version and capability documentation**

Set package version constants and lock metadata to `0.3.1`. Update `SKILL.md` to describe compact ranked views, decision reconstruction, independent measures, report ceilings, and evidence appendix navigation.

- [ ] **Step 2: Run release verification**

Run: `uv sync --frozen`  
Expected: success.

Run: `uv run pytest -q`  
Expected: all tests PASS.

Run: `uv build`  
Expected: wheel and source distribution build successfully.

Run: `git diff --check`  
Expected: no output.

- [ ] **Step 3: Commit release readiness**

```bash
git add pyproject.toml scripts/architecture_graph/__init__.py SKILL.md uv.lock
git commit -m "chore: prepare architecture graph 0.3.1"
```

- [ ] **Step 4: Request final code review and resolve every critical or important finding**

Review the diff from `4e5006a` through `HEAD` against the Phase 2.1 specification and this plan. Repeat focused and full tests after fixes.

- [ ] **Step 5: Push and open the approved pull request**

```bash
git push -u origin design/phase-2-1-ranked-retrieval
gh pr create --base main --head design/phase-2-1-ranked-retrieval --title "Phase 2.1: rank the full architecture corpus with bounded evidence retrieval" --body-file /tmp/architecture-graph-phase-2-1-pr.md
```

The PR body must describe the real-world failure, full-analysis/compact-view architecture, decision reconstruction, independent measures, report appendix, compatibility, tests, and release version.
