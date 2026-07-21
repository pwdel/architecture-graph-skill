# Phase 2 Evidence Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, prose-first evidence graph that exposes terms, bounded graph traversal, source-backed decisions, explanations, and an engineer report without an LLM reading the full corpus.

**Architecture:** Phase 1 adapters continue to normalize Markdown, plaintext, Mermaid, PlantUML, YAML, and JSON into segments and evidence. Phase 2 runs immutable analysis stages over that common evidence, publishes typed semantic records in the existing atomic snapshot, then serves bounded commands from the published snapshot. Graph navigation ships before decision reduction and reporting; navigation, criticality, review priority, and extraction confidence use independent versioned feature sets.

**Tech Stack:** Python 3.12, standard library sparse vectors and graph algorithms, PyYAML, jsonlines, jmespath, pytest; no network, model download, embeddings, vector database, provider SDK, or runtime LLM.

This plan supersedes the release boundary and task order in `docs/superpowers/plans/2026-07-19-architecture-graph-phase-2-analysis.md`. Engineers may consult that plan for background, but must follow this graph-first sequence and its narrower release boundary.

## Global Constraints

- Treat prose and text-native diagrams through one semantic model; format adapters may add provenance but cannot create format-specific semantic records.
- Support Markdown and ADR prose, selected plaintext, Mermaid, PlantUML, YAML, and JSON. Exclude raster images, screenshots, scanned diagrams, and visual PDF interpretation.
- Keep analysis deterministic and offline. Indexing must not open a network socket or download an artifact.
- Persist evidence and derivation IDs for every claim, semantic edge, decision, score feature, explanation, and report assertion.
- Count distinct source content hashes, not paths, for corroboration, evidence breadth, term document frequency, edge strength, or rank features.
- Keep navigation, criticality, review priority, and extraction confidence as independent scores. Graph centrality cannot define criticality.
- Keep incomplete tuples as candidates plus warnings. Do not publish them as claims.
- Similarity may emit alias candidates. Only explicit IDs, declared aliases, exact canonical keys, and unambiguous acronyms may merge entities.
- Keep proposals as proposals unless accepted source status authorizes a current commitment.
- Clamp finite scores to `[0, 1]`, round to eight decimal places, and persist rule versions and feature inputs.
- Resolve one immutable snapshot per read command. Bind cursors to the snapshot, command, normalized arguments, fields, filters, score, output format, and budgets.
- Defer human-review mutation, semantic snapshot diff, and long-term decision lineage.
- Run each task test-first. Commit only after focused and cumulative tests pass.

## File Map

### Analysis core

- `scripts/architecture_graph/analysis_types.py`: immutable stage values, normalized evidence objects, result objects, and record catalog.
- `scripts/architecture_graph/schemas.py`: Phase 2 record validation and versioned resource loading.
- `scripts/architecture_graph/nlp.py`: deterministic tokenizer, sentence splitting, phrase extraction, and optional local-model fallback boundary.
- `scripts/architecture_graph/terms.py`: sparse TF-IDF, glossary signals, and term records.
- `scripts/architecture_graph/relations.py`: prose and text-diagram relation candidates.
- `scripts/architecture_graph/qualifiers.py`: modality, polarity, conditions, scope, time, role, and source-status qualifiers.
- `scripts/architecture_graph/entities.py`: conservative entity resolution and alias warnings.
- `scripts/architecture_graph/claims.py`: qualified claim promotion and canonical claim records.
- `scripts/architecture_graph/semantic_graph.py`: typed nodes, typed edges, evidence-backed edge construction, and bounded adjacency.
- `scripts/architecture_graph/ranking.py`: independent navigation, criticality, review-priority, and extraction-confidence scoring.
- `scripts/architecture_graph/decisions.py`: source-anchored decision reduction.
- `scripts/architecture_graph/analysis.py`: ordered corpus-global pipeline and record validation.
- `scripts/architecture_graph/report.py`: evidence-linked engineer report model and text renderer.

### Commands and integration

- `scripts/architecture_graph/capabilities.py`: machine-readable implemented-feature contract.
- `scripts/architecture_graph/semantic_queries.py`: terms, neighbors, decisions, evidence, explain, and report query functions.
- `scripts/architecture_graph/paging.py`: complete-item character fitting and query-bound cursors.
- `scripts/architecture_graph/indexer.py`: run Phase 2 before atomic publication.
- `scripts/architecture_graph/cli.py`: expose the seven Phase 2 commands.
- `scripts/architecture_graph/records.py`: Phase 2 required fields and reference validation hooks.
- `scripts/architecture_graph/snapshot.py`: validate all Phase 2 records and references before publication.
- `scripts/architecture_graph/fingerprint.py`: include analysis rules and resources in the pipeline digest.

### Versioned resources and tests

- `scripts/architecture_graph/resources/{terms-en-v1,predicates-v1,extraction-rules-en-v1,entity-rules-v1,decision-rules-v1,scoring-v1}.json`: deterministic rule data.
- `tests/helpers/phase2_catalog.py`: compact valid semantic record factory.
- `tests/helpers/phase2_snapshot.py`: published semantic snapshot fixture.
- `tests/fixtures/phase2_repo/`: mixed prose, ADR, Mermaid, PlantUML, YAML, JSON, duplicate-content, conflict, and missing-rationale corpus.
- `tests/fixtures/golden/phase2/`: canonical manifest, semantic JSONL, capabilities JSON, and report.
- `tests/test_{analysis_types,nlp,terms,relations,claims,semantic_graph,ranking,decisions,semantic_queries,phase2_cli,phase2_golden}.py`: focused and acceptance coverage.

---

### Task 1: Typed Records, Resources, and Capabilities

**Files:**
- Create: `scripts/architecture_graph/analysis_types.py`
- Create: `scripts/architecture_graph/schemas.py`
- Create: `scripts/architecture_graph/capabilities.py`
- Create: `scripts/architecture_graph/resources/__init__.py`
- Create: `scripts/architecture_graph/resources/terms-en-v1.json`
- Create: `scripts/architecture_graph/resources/predicates-v1.json`
- Create: `scripts/architecture_graph/resources/extraction-rules-en-v1.json`
- Create: `scripts/architecture_graph/resources/entity-rules-v1.json`
- Create: `scripts/architecture_graph/resources/decision-rules-v1.json`
- Create: `scripts/architecture_graph/resources/scoring-v1.json`
- Modify: `scripts/architecture_graph/records.py`
- Modify: `scripts/architecture_graph/cli.py`
- Modify: `scripts/architecture_graph/fingerprint.py`
- Modify: `pyproject.toml`
- Create: `tests/helpers/phase2_catalog.py`
- Create: `tests/test_analysis_types.py`
- Create: `tests/test_capabilities.py`

**Interfaces:**
- Produces `EvidenceUnit`, `ParsedSentence`, `RelationCandidate`, `QualifiedRelation`, `ClaimArgument`, `RecordCatalog`, and `AnalysisResult` frozen dataclasses.
- Produces `load_versioned_resource(name: str) -> Mapping[str, object]`, `resource_digest(name: str) -> str`, `validate_typed_record(record: Mapping[str, object], expected_kind: str | None = None) -> tuple[ValidationIssue, ...]`, and `validate_snapshot_references(records_by_type: Mapping[str, Sequence[Record]]) -> tuple[ValidationIssue, ...]`.
- Produces `capability_record() -> Record` and CLI `architecture-graph capabilities --json`.

- [ ] **Step 1: Write failing type, schema, resource, and capabilities tests**

Create tests that construct every Phase 2 record through `valid_typed_record(kind)`, reject a missing `evidence_ids` or `derivation_ids`, reject an unknown node or edge type, prove resource digests are stable, and assert this exact capability surface:

```python
def test_capabilities_advertise_only_implemented_phase_two_commands() -> None:
    item = capability_record()
    assert item["phases"] == ["phase1", "phase2"]
    assert item["commands"] == [
        "capabilities", "decisions", "evidence", "explain", "find",
        "get", "index", "memory status", "neighbors", "report", "terms",
    ]
    assert item["unavailable"] == [
        "human_review_mutation", "image_interpretation",
        "semantic_snapshot_diff", "decision_lineage",
    ]
```

Run: `uv run pytest tests/test_analysis_types.py tests/test_capabilities.py -q`  
Expected: FAIL because the Phase 2 modules do not exist.

- [ ] **Step 2: Implement immutable values and a collision-safe catalog**

Implement the dataclasses with validated discriminators and tuple-backed collections. Implement `RecordCatalog.from_records()` so byte-identical duplicate IDs deduplicate and different content under one ID raises `ValueError("duplicate record id with different content")`. Implement `add()`, `iter(kind)`, `get(id)`, and `records_by_type()` with canonical ID ordering.

- [ ] **Step 3: Implement typed schemas and versioned resources**

Define required fields for `term`, `entity`, `claim`, `decision`, `edge`, `ranking`, `warning`, and `derivation`. Validate ID prefixes, enums, finite scores, score bounds, canonical ordering, evidence references, derivation references, node endpoints, and content digests. Store stop words, controlled predicates, qualifier markers, entity rules, decision headings/statuses, and score weights in package JSON. Add `resources/*.json` as setuptools package data.

- [ ] **Step 4: Implement capabilities and fingerprint integration**

Return a finalized `capability:phase2` record containing schema version, phases, commands, record types, node types, edge types, provenance layers, rule versions, and unavailable features. Add only `capabilities` to the CLI in this task. Include all resource digests and the semantic schema version in `pipeline_fingerprint()`.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/test_analysis_types.py tests/test_capabilities.py tests/test_canonical.py tests/test_cli_smoke.py -q`  
Expected: PASS.

```bash
git add pyproject.toml scripts/architecture_graph tests/helpers/phase2_catalog.py tests/test_analysis_types.py tests/test_capabilities.py
git commit -m "feat: define Phase 2 semantic contracts"
```

### Task 2: Deterministic Normalized Text Runtime

**Files:**
- Create: `scripts/architecture_graph/nlp.py`
- Create: `tests/test_nlp.py`
- Modify: `scripts/architecture_graph/resources/extraction-rules-en-v1.json`

**Interfaces:**
- Consumes Phase 1 source, segment, evidence, and derivation records.
- Produces `normalize_evidence(catalog: RecordCatalog) -> tuple[EvidenceUnit, ...]` and `parse_evidence(units: Sequence[EvidenceUnit], model_name: str | None = None) -> ParsedCorpus`.
- `ParsedCorpus` exposes canonical sentences, tokens, noun phrases, acronyms, diagram endpoints, diagram labels, and warning records.

- [ ] **Step 1: Write failing prose, diagram, structured-value, and model-fallback tests**

```python
def test_all_formats_share_parsed_sentence_contract(mixed_catalog):
    parsed = parse_evidence(normalize_evidence(mixed_catalog))
    assert {item.format_kind for item in parsed.sentences} == {
        "markdown", "plaintext", "mermaid", "plantuml", "yaml", "json"
    }
    assert all(item.evidence_id and item.derivation_id for item in parsed.sentences)

def test_missing_model_uses_rules_without_download(mixed_catalog, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *args: (_ for _ in ()).throw(AssertionError("network")))
    parsed = parse_evidence(normalize_evidence(mixed_catalog), "missing-local-model")
    assert any(w["code"] == "model_unavailable" for w in parsed.warnings)
    assert parsed.sentences
```

Run: `uv run pytest tests/test_nlp.py -q`  
Expected: FAIL because `architecture_graph.nlp` does not exist.

- [ ] **Step 2: Implement evidence normalization**

Map paragraphs, headings, list items, diagram nodes, diagram edges, metadata fields, and structured scalars into `EvidenceUnit`. Preserve source-content hash, exact span, original text, heading path, section role, document role, authority, status, adapter name/version, and format metadata such as JSON pointer, YAML path, or diagram node ID.

- [ ] **Step 3: Implement the no-download parser**

Use Unicode normalization, versioned token regexes, sentence terminators, heading boundaries, list boundaries, capitalized phrase runs, acronym patterns, and adapter-provided diagram endpoints. If `model_name` cannot load from an installed local package, emit one bounded `model_unavailable` warning and run the rules. Never invoke a package installer, URL loader, or model downloader.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_nlp.py tests/test_other_ingest.py tests/test_markdown_ingest.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/nlp.py scripts/architecture_graph/resources/extraction-rules-en-v1.json tests/test_nlp.py
git commit -m "feat: normalize architecture prose and diagrams"
```

### Task 3: Sparse TF-IDF and Glossary Candidates

**Files:**
- Create: `scripts/architecture_graph/terms.py`
- Create: `tests/test_terms.py`
- Modify: `scripts/architecture_graph/resources/terms-en-v1.json`

**Interfaces:**
- Consumes `ParsedCorpus`.
- Produces `discover_terms(parsed: ParsedCorpus) -> TermResult` where `TermResult` contains term records, warning records, derivations, and `weights_by_evidence_id`.

- [ ] **Step 1: Write failing term discovery tests**

```python
def test_tfidf_counts_distinct_content_hashes_once(parsed_duplicate_corpus):
    result = discover_terms(parsed_duplicate_corpus)
    gateway = next(x for x in result.terms if x["canonical_form"] == "gateway")
    assert gateway["distinct_source_count"] == 1

def test_glossary_headings_acronyms_and_diagram_labels_add_signals(parsed_corpus):
    result = discover_terms(parsed_corpus)
    terms = {x["canonical_form"]: x for x in result.terms}
    assert {"api gateway", "slo"} <= terms.keys()
    assert "explicit_glossary" in terms["api gateway"]["discovery_signals"]
    assert "acronym" in terms["slo"]["discovery_signals"]
```

Run: `uv run pytest tests/test_terms.py -q`  
Expected: FAIL because `discover_terms` does not exist.

- [ ] **Step 2: Implement sparse TF-IDF**

Build one document per distinct `source_content_hash`. Compute lowercase canonical unigrams and noun phrases after stop-word filtering. Use `tf = 1 + log(count)` and `idf = log((1 + document_count) / (1 + document_frequency)) + 1`. Add bounded bonuses from explicit glossary sections, headings, acronyms, diagram labels, and meaningful structured values. Canonically sort ties by canonical form.

- [ ] **Step 3: Materialize source-backed term records**

Persist canonical form, observed forms, term kind, evidence IDs, distinct source count, document frequency, TF-IDF summary, discovery signals, and derivation IDs. Cap evidence per term through a versioned resource value while retaining the full distinct-source count.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_terms.py tests/test_nlp.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/terms.py scripts/architecture_graph/resources/terms-en-v1.json tests/test_terms.py
git commit -m "feat: discover architecture vocabulary"
```

### Task 4: Qualified Relations, Conservative Entities, and Claims

**Files:**
- Create: `scripts/architecture_graph/relations.py`
- Create: `scripts/architecture_graph/qualifiers.py`
- Create: `scripts/architecture_graph/entities.py`
- Create: `scripts/architecture_graph/claims.py`
- Create: `tests/test_relations.py`
- Create: `tests/test_claims.py`
- Modify: `scripts/architecture_graph/resources/predicates-v1.json`
- Modify: `scripts/architecture_graph/resources/entity-rules-v1.json`

**Interfaces:**
- Produces `extract_relation_candidates(parsed: ParsedCorpus) -> RelationResult`.
- Produces `qualify_relations(candidates: Sequence[RelationCandidate], parsed: ParsedCorpus) -> tuple[QualifiedRelation, ...]`.
- Produces `resolve_entities(relations: Sequence[QualifiedRelation], terms: TermResult) -> EntityResult`.
- Produces `materialize_claims(relations: Sequence[QualifiedRelation], entities: EntityResult) -> ClaimResult`.

- [ ] **Step 1: Write failing prose, diagram, qualifier, and ambiguity tests**

```python
def test_prose_and_diagram_claims_share_schema(parsed_corpus, term_result):
    relations = extract_relation_candidates(parsed_corpus)
    qualified = qualify_relations(relations.candidates, parsed_corpus)
    entities = resolve_entities(qualified, term_result)
    claims = materialize_claims(qualified, entities).claims
    prose = next(x for x in claims if x["parser_provenance"] == "rule_prose")
    diagram = next(x for x in claims if x["parser_provenance"] == "diagram_edge")
    assert set(prose) == set(diagram)
    assert prose["evidence_ids"] != diagram["evidence_ids"]

def test_incomplete_tuple_and_fuzzy_alias_never_create_claim(parsed_corpus, term_result):
    relations = extract_relation_candidates(parsed_corpus)
    qualified = qualify_relations(relations.candidates, parsed_corpus)
    entities = resolve_entities(qualified, term_result)
    result = materialize_claims(qualified, entities)
    assert any(w["code"] == "incomplete_relation" for w in result.warnings)
    assert any(w["code"] == "alias_candidate" for w in entities.warnings)
    assert all(x["tuple_complete"] for x in result.claims)
```

Run: `uv run pytest tests/test_relations.py tests/test_claims.py -q`  
Expected: FAIL because the extraction modules do not exist.

- [ ] **Step 2: Extract controlled relation candidates**

For prose, match controlled predicate surfaces around explicit noun phrases and retain unmatched predicate text as a candidate warning. For Mermaid and PlantUML, use adapter endpoints as subject and object and normalize the edge label as predicate. Preserve the original sentence or edge label and exact evidence ID.

- [ ] **Step 3: Attach qualifiers before claim promotion**

Attach modality, polarity, conditions, scope, time applicability, section role, document status, authority, and parser provenance using versioned markers. Treat headings such as Proposed, Deprecated, Alternatives, and Consequences as lifecycle evidence. Keep unknown values explicit rather than inferring acceptance.

- [ ] **Step 4: Resolve only conservative entities**

Use explicit structured IDs, declared glossary aliases, exact canonical keys, and acronyms with one expansion. Emit `alias_candidate` for edit-distance or token-similarity suggestions and keep both entities. Represent non-entity objects as typed literal `ClaimArgument` values.

- [ ] **Step 5: Promote complete relations to claims**

Require subject, controlled predicate, object, polarity, modality, applicability, evidence, and derivation. Generate claim identity from normalized semantic fields plus source anchor, not path spelling. Merge byte-identical corroboration by content hash and retain all evidence paths for citation.

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/test_relations.py tests/test_claims.py tests/test_terms.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/relations.py scripts/architecture_graph/qualifiers.py scripts/architecture_graph/entities.py scripts/architecture_graph/claims.py scripts/architecture_graph/resources tests/test_relations.py tests/test_claims.py
git commit -m "feat: extract qualified architecture claims"
```

### Task 5: Typed Evidence Graph

**Files:**
- Create: `scripts/architecture_graph/semantic_graph.py`
- Create: `tests/test_semantic_graph.py`

**Interfaces:**
- Consumes sources, segments, evidence, terms, entities, claims, warnings, and derivations.
- Produces `build_evidence_graph(catalog: RecordCatalog) -> GraphResult` and `bounded_neighbors(graph: GraphResult, node_id: str, depth: int, limit: int) -> NeighborResult`.
- Node types: `source`, `segment`, `evidence`, `term`, `entity`, `claim`, `decision`, `warning`, `derivation`.
- Edge types: `CONTAINS`, `MENTIONS`, `ASSERTS`, `SUBJECT_OF`, `OBJECT_OF`, `SUPPORTS`, `CONTRADICTS`, `QUALIFIES`, `DERIVED_FROM`, `RELATED_TO`.

- [ ] **Step 1: Write failing graph provenance and traversal tests**

```python
def test_every_semantic_edge_resolves_to_evidence_or_derivation(semantic_catalog):
    graph = build_evidence_graph(semantic_catalog)
    for edge in graph.edges:
        assert edge["evidence_ids"] or edge["derivation_ids"]
        assert graph.catalog.get(edge["from_id"])
        assert graph.catalog.get(edge["to_id"])

def test_bounded_neighbors_are_stable_and_cycle_safe(semantic_catalog):
    graph = build_evidence_graph(semantic_catalog)
    first = bounded_neighbors(graph, "entity:gateway", depth=2, limit=20)
    second = bounded_neighbors(graph, "entity:gateway", depth=2, limit=20)
    assert first == second
    assert max(x["depth"] for x in first.nodes) <= 2
    assert len({x["id"] for x in first.nodes}) == len(first.nodes)
```

Run: `uv run pytest tests/test_semantic_graph.py -q`  
Expected: FAIL because `semantic_graph` does not exist.

- [ ] **Step 2: Materialize graph nodes and evidence-backed edges**

Project existing records as nodes without changing their identities. Build containment, mention, assertion, claim-argument, qualification, support, contradiction, derivation, and low-confidence related edges. Require evidence for semantic edges and derivations for computed edges. Deduplicate edge identity from type, endpoints, semantic anchor, and distinct supporting content hashes.

- [ ] **Step 3: Implement bounded adjacency**

Build sorted in-memory adjacency from persisted edges. Traverse breadth-first, record depth and direction, reject depth below zero or above the configured maximum, stop at the item limit, and order each frontier by edge type then opposite-node ID. Return complete nodes and connecting edges only.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_semantic_graph.py tests/test_claims.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/semantic_graph.py tests/test_semantic_graph.py
git commit -m "feat: build typed architecture evidence graph"
```

### Task 6: Independent Graph and Evidence Rankings

**Files:**
- Create: `scripts/architecture_graph/ranking.py`
- Create: `tests/test_ranking.py`
- Modify: `scripts/architecture_graph/resources/scoring-v1.json`

**Interfaces:**
- Produces `rank_graph(graph: GraphResult, catalog: RecordCatalog) -> RankingResult`.
- Produces one `ranking` record per eligible node with `navigation`, `criticality`, `review_priority`, and `extraction_confidence`, each containing score, rule version, feature vector, and derivation ID.

- [ ] **Step 1: Write failing score-separation and duplicate tests**

```python
def test_navigation_centrality_does_not_define_criticality(ranking_catalog):
    ranks = rank_graph(build_evidence_graph(ranking_catalog), ranking_catalog).by_node
    assert ranks["entity:gateway"]["navigation"]["score"] > ranks["claim:encrypt"]["navigation"]["score"]
    assert ranks["claim:encrypt"]["criticality"]["score"] > ranks["entity:gateway"]["criticality"]["score"]

def test_duplicate_source_bytes_do_not_change_scores(ranking_catalog, duplicated_catalog):
    left = rank_graph(build_evidence_graph(ranking_catalog), ranking_catalog)
    right = rank_graph(build_evidence_graph(duplicated_catalog), duplicated_catalog)
    assert left.semantic_scores() == right.semantic_scores()
```

Run: `uv run pytest tests/test_ranking.py -q`  
Expected: FAIL because `rank_graph` does not exist.

- [ ] **Step 2: Implement navigation features**

Compute typed in/out degree, bounded harmonic centrality, distinct-content evidence breadth, cross-boundary connections, claim participation, decision participation when available, glossary relevance, contradiction links, and lifecycle eligibility. Normalize each feature independently. Apply `scoring-v1.json` weights and prevent raw mention count from entering the score.

- [ ] **Step 3: Implement independent consequence, review, and confidence features**

Criticality uses authority, modality, scope, affected boundaries, evidence breadth, and structural-impact predicates. Review priority uses missing rationale, contradictions, unresolved scope, weak evidence, and low extraction confidence. Extraction confidence uses parser provenance, tuple completeness, explicit structure, source quality, and distinct-content corroboration. Do not reuse navigation score as an input.

- [ ] **Step 4: Persist explainable score records**

Reject NaN and infinity, clamp, round to eight places, and store raw inputs, normalized features, weights, rule digest, eligible content hashes, excluded duplicate paths, and derivation ID. Add an invariant test that recalculates every score from the stored vector.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/test_ranking.py tests/test_semantic_graph.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/ranking.py scripts/architecture_graph/resources/scoring-v1.json tests/test_ranking.py
git commit -m "feat: rank architecture graph with independent scores"
```

### Task 7: Source-Anchored Decision Reduction

**Files:**
- Create: `scripts/architecture_graph/decisions.py`
- Create: `tests/test_decisions.py`
- Modify: `scripts/architecture_graph/resources/decision-rules-v1.json`
- Modify: `scripts/architecture_graph/semantic_graph.py`
- Modify: `scripts/architecture_graph/ranking.py`

**Interfaces:**
- Produces `reduce_decisions(catalog: RecordCatalog, graph: GraphResult) -> DecisionResult`.
- Produces `attach_decisions(graph: GraphResult, decisions: DecisionResult) -> GraphResult`.
- Produces `rerank_decisions(graph: GraphResult, catalog: RecordCatalog, prior: RankingResult) -> RankingResult` without changing non-decision semantic scores.

- [ ] **Step 1: Write failing accepted/proposed/rationale/conflict tests**

```python
def test_proposal_cannot_become_current_decision(decision_catalog):
    result = reduce_decisions(decision_catalog, build_evidence_graph(decision_catalog))
    proposed = next(x for x in result.decisions if x["title"] == "Adopt queues")
    assert proposed["status"] == "proposed"
    assert proposed["applicability"] != "current"

def test_missing_rationale_and_conflict_raise_review_priority(decision_catalog):
    result = reduce_decisions(decision_catalog, build_evidence_graph(decision_catalog))
    decision = next(x for x in result.decisions if x["title"] == "Choose gateway")
    assert decision["rationale_evidence_ids"] == []
    assert "missing_rationale" in decision["diagnostic_codes"]
    assert decision["contradicting_claim_ids"]
```

Run: `uv run pytest tests/test_decisions.py -q`  
Expected: FAIL because `decisions` does not exist.

- [ ] **Step 2: Implement source-anchor reduction**

Group claims by explicit ADR ID, structured decision ID, or exact normalized decision heading plus scope. Reduce status using versioned authority ordering and document lifecycle. Preserve title, status, applicability, scope, decision claims, rationale evidence, consequence evidence, supporting and contradicting claims, authority, source-content hashes, and derivations. Emit diagnostics instead of invented rationale.

- [ ] **Step 3: Add decisions to the graph and rankings**

Create decision nodes and `ASSERTS`, `SUPPORTS`, `CONTRADICTS`, and `DERIVED_FROM` edges. Recompute affected navigation features and calculate all four decision scores from independent feature vectors. Assert that adding decision nodes cannot mutate existing claim criticality or confidence.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_decisions.py tests/test_ranking.py tests/test_semantic_graph.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/decisions.py scripts/architecture_graph/semantic_graph.py scripts/architecture_graph/ranking.py scripts/architecture_graph/resources/decision-rules-v1.json tests/test_decisions.py
git commit -m "feat: reduce source-backed architecture decisions"
```

### Task 8: Corpus-Global Analysis and Atomic Publication

**Files:**
- Create: `scripts/architecture_graph/analysis.py`
- Modify: `scripts/architecture_graph/indexer.py`
- Modify: `scripts/architecture_graph/snapshot.py`
- Modify: `scripts/architecture_graph/records.py`
- Create: `tests/test_analysis.py`
- Create: `tests/test_phase2_publication.py`

**Interfaces:**
- Produces `analyze_catalog(phase1: RecordCatalog, *, model_name: str | None = None) -> AnalysisResult`.
- `AnalysisResult.records_by_type()` returns canonical `terms`, `entities`, `claims`, `decisions`, `edges`, `rankings`, `derivations`, and `warnings`.
- `index_corpus()` remains the only publisher.

- [ ] **Step 1: Write failing orchestration, invalid-record, and atomicity tests**

```python
def test_analysis_pipeline_order_and_reference_closure(phase1_catalog):
    result = analyze_catalog(phase1_catalog)
    records = result.records_by_type()
    assert records["terms"] and records["edges"] and records["rankings"]
    assert validate_snapshot_references(records) == ()

def test_invalid_semantic_record_leaves_current_pointer_unchanged(project, monkeypatch):
    before = project.current_path.read_bytes()
    monkeypatch.setattr("architecture_graph.analysis.analyze_catalog", invalid_analysis)
    with pytest.raises(ValueError, match="semantic snapshot validation"):
        index_corpus([project.repository])
    assert project.current_path.read_bytes() == before
```

Run: `uv run pytest tests/test_analysis.py tests/test_phase2_publication.py -q`  
Expected: FAIL because orchestration and publication integration do not exist.

- [ ] **Step 2: Implement the exact pipeline order**

Run normalization, parsing, terms, relations, qualifiers, entities, claims, base graph, base ranking, decisions, decision graph attachment, and final ranking. Combine stage derivations and warnings in `RecordCatalog`; reject ID collisions and unresolved references after each stage.

- [ ] **Step 3: Integrate before snapshot publication**

Build Phase 1 records exactly as v0.2.0 does, pass them to `analyze_catalog`, merge semantic records by record type, validate typed shapes and complete references, then create `SnapshotBundle`. Any analysis or validation error must occur before snapshot directory publication, observation append, or current-pointer replacement.

- [ ] **Step 4: Prove corpus-global refresh and snapshot reuse**

Add a test that edits one local source and verifies corpus-global term document frequencies, graph edges, and scores recompute. Add a second test that unchanged material inputs and rule digests reuse the snapshot byte-for-byte.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/test_analysis.py tests/test_phase2_publication.py tests/test_snapshot.py tests/test_phase1_cli.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/analysis.py scripts/architecture_graph/indexer.py scripts/architecture_graph/snapshot.py scripts/architecture_graph/records.py tests/test_analysis.py tests/test_phase2_publication.py
git commit -m "feat: publish semantic analysis atomically"
```

### Task 9: Stable Paging and Semantic Queries

**Files:**
- Create: `scripts/architecture_graph/paging.py`
- Create: `scripts/architecture_graph/semantic_queries.py`
- Create: `tests/helpers/phase2_snapshot.py`
- Create: `tests/test_semantic_queries.py`

**Interfaces:**
- Produces `terms_query`, `neighbors_query`, `decisions_query`, `evidence_query`, and `explain_query`; each accepts a resolved `SnapshotReader`, command-specific selectors, `fields`, `limit`, `max_chars`, and optional cursor.
- Produces `fit_complete_items(items: Sequence[Record], binding: CursorBinding, max_chars: int) -> QueryEnvelope`.

- [ ] **Step 1: Write failing bounded-query and cursor tests**

```python
def test_cursor_resumes_after_last_emitted_item(phase2_reader):
    first = decisions_query(phase2_reader, score="navigation", limit=20, max_chars=900)
    second = decisions_query(phase2_reader, score="navigation", limit=20, max_chars=900, cursor=first.cursor)
    assert first.items
    assert second.items
    assert set(x["id"] for x in first.items).isdisjoint(x["id"] for x in second.items)

def test_neighbor_query_hydrates_citable_evidence(phase2_reader):
    result = neighbors_query(phase2_reader, node_id="entity:gateway", depth=2, limit=20, evidence_limit=2, max_chars=12_000)
    assert result.items[0]["source_path"]
    assert result.items[0]["span"]["start_line"] >= 1
    assert result.items[0]["evidence_ids"]
```

Run: `uv run pytest tests/test_semantic_queries.py -q`  
Expected: FAIL because the semantic query layer does not exist.

- [ ] **Step 2: Implement complete-item fitting and bound cursors**

Fit serialized records without slicing an item. If the next record exceeds `max_chars`, return a cursor positioned before that record. Bind a SHA-256 digest to snapshot ID, command, normalized selectors, fields, filters, score, item limit, graph depth, evidence limit, character budget, and output format. Reject mismatched or stale cursors with a distinct error.

- [ ] **Step 3: Implement terms, neighbors, and decisions queries**

Sort terms by requested TF-IDF or source count; neighbors by depth, navigation score, edge type, then ID; decisions by requested independent score then ID. Enforce configured maximum depth and limit. Hydrate path, span, bounded evidence text, evidence IDs, derivation IDs, and score explanation fields from the same snapshot.

- [ ] **Step 4: Implement evidence and explain queries**

`evidence --for ID` resolves direct and supporting evidence with distinct-content metadata. `explain --id ID` returns the record, derivation chain, semantic neighbors, score feature vectors, included content hashes, excluded duplicates, diagnostics, and bounded evidence. Detect derivation cycles and return each record once.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/test_semantic_queries.py tests/test_query.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/paging.py scripts/architecture_graph/semantic_queries.py tests/helpers/phase2_snapshot.py tests/test_semantic_queries.py
git commit -m "feat: query bounded architecture evidence"
```

### Task 10: Evidence-Linked Engineer Report

**Files:**
- Create: `scripts/architecture_graph/report.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Produces `build_report(reader: SnapshotReader, *, limits: ReportLimits) -> ReportResult` and `render_report_text(result: ReportResult) -> str`.
- `ReportResult` contains assertion records plus rendered sections; every assertion contains evidence IDs and derivation IDs.

- [ ] **Step 1: Write failing report content and low-coverage tests**

```python
def test_report_assertions_are_citable(phase2_reader):
    report = build_report(phase2_reader, limits=ReportLimits.defaults())
    assert report.assertions
    assert all(x["evidence_ids"] and x["derivation_ids"] for x in report.assertions)
    text = render_report_text(report)
    assert "Navigation hubs" in text
    assert "Critical decisions and constraints" in text
    assert "Review priorities" in text

def test_empty_semantic_stages_report_coverage_instead_of_silence(empty_reader):
    text = render_report_text(build_report(empty_reader, limits=ReportLimits.defaults()))
    assert "Coverage" in text
    assert "No qualified claims were extracted" in text
```

Run: `uv run pytest tests/test_report.py -q`  
Expected: FAIL because `report` does not exist.

- [ ] **Step 2: Build report assertions from bounded queries**

Select high-navigation nodes, high-criticality decisions and constraints, high-review-priority gaps, contradictions, missing rationale, unresolved scope, glossary candidates, and prose/diagram agreement or disagreement. Each assertion must cite path, span, evidence ID, derivation ID, and extraction confidence. Use stable limits from `ReportLimits`.

- [ ] **Step 3: Render deterministic engineer text**

Render metadata and coverage first, followed by Navigation hubs, Critical decisions and constraints, Review priorities, Conflicts and weak rationale, Unresolved scope, Glossary candidates, and Prose and diagram agreement. Sort ties by record ID. Mark low-confidence assertions in the same bullet as their citation.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_report.py tests/test_semantic_queries.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/report.py tests/test_report.py
git commit -m "feat: render evidence-linked architecture reports"
```

### Task 11: Phase 2 CLI Surface

**Files:**
- Modify: `scripts/architecture_graph/cli.py`
- Modify: `bin/architecture-graph`
- Create: `tests/test_phase2_cli.py`

**Interfaces:**
- Adds the approved commands: `terms ROOT`, `neighbors ROOT`, `decisions ROOT`, `evidence ROOT`, `explain ROOT`, and `report ROOT`.
- Reuses `--memory-root`, `--corpus`, `--snapshot`, `--fields`, `--limit`, `--cursor`, `--max-chars`, and `--json` consistently.

- [ ] **Step 1: Write failing parser and end-to-end CLI tests**

```python
@pytest.mark.parametrize("command", ["terms", "neighbors", "decisions", "evidence", "explain", "report"])
def test_phase2_command_is_advertised(command):
    result = run_cli(command, "--help")
    assert result.returncode == 0

def test_decisions_cli_reads_published_snapshot(indexed_phase2_repo):
    result = run_cli("decisions", str(indexed_phase2_repo), "--score", "criticality", "--json")
    payload = json.loads(result.stdout)
    assert payload["items"]
    assert payload["items"][0]["scores"]["criticality"]["score"] >= payload["items"][-1]["scores"]["criticality"]["score"]
```

Run: `uv run pytest tests/test_phase2_cli.py -q`  
Expected: FAIL because the parsers are absent.

- [ ] **Step 2: Add consistent parsers and dispatch**

Require `--node` and `--depth` for neighbors, `--for` for evidence, `--id` for explain, and allow `--score {navigation,criticality,review_priority,extraction_confidence}` for decisions. Resolve repository, corpus, and immutable snapshot once through a shared helper. Render canonical JSON envelopes for `--json`; render concise tables for terms, neighbors, decisions, evidence, and explain; render engineer text for report.

- [ ] **Step 3: Return distinct user-facing failures**

Map missing memory, stale/mismatched cursor, absent node, unavailable capability, invalid depth, exceeded bounds, and corrupt semantic records to separate `ArchitectureGraphError` codes and exit code 2. Keep unexpected internal failures at exit code 1 without a traceback unless debug mode exists.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_phase2_cli.py tests/test_cli_smoke.py tests/test_phase1_cli.py -q`  
Expected: PASS.

```bash
git add scripts/architecture_graph/cli.py bin/architecture-graph tests/test_phase2_cli.py
git commit -m "feat: expose Phase 2 graph commands"
```

### Task 12: Mixed-Format Golden Acceptance and Skill Handoff

**Files:**
- Create: `tests/fixtures/phase2_repo/architecture/overview.md`
- Create: `tests/fixtures/phase2_repo/architecture/ADR-001-gateway.md`
- Create: `tests/fixtures/phase2_repo/architecture/flow.mmd`
- Create: `tests/fixtures/phase2_repo/architecture/sequence.puml`
- Create: `tests/fixtures/phase2_repo/architecture/services.yaml`
- Create: `tests/fixtures/phase2_repo/architecture/policies.json`
- Create: `tests/fixtures/phase2_repo/architecture/duplicate-overview.md`
- Create: `tests/fixtures/golden/phase2/`
- Create: `tests/test_phase2_golden.py`
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/agent-usage.md`
- Modify: `agents/openai.yaml`

**Interfaces:**
- Produces a byte-stable mixed-format acceptance corpus and expected snapshot.
- Documents the capability-first agent workflow and the Phase 2 release boundary.

- [ ] **Step 1: Create the adversarial mixed-format fixture and failing golden test**

The fixture must include ordinary prose, an accepted ADR with rationale, an unresolved proposal, a low-degree encryption constraint, a missing-rationale decision, one prose/diagram agreement, one contradiction, Mermaid and PlantUML edges, YAML and JSON structure, two paths with identical bytes, and an ambiguous alias. Assert:

```python
def test_phase2_mixed_format_golden_is_deterministic(tmp_path):
    first = index_fixture_copy(tmp_path / "first")
    second = index_fixture_copy(tmp_path / "second")
    assert semantic_bytes(first) == semantic_bytes(second)
    assert semantic_bytes(first) == golden_semantic_bytes()

def test_phase2_acceptance_contract(indexed_fixture):
    assert useful_terms(indexed_fixture)
    assert prose_and_diagram_claims_share_schema(indexed_fixture)
    assert duplicate_bytes_do_not_inflate_scores(indexed_fixture)
    assert low_degree_encryption_constraint_is_critical(indexed_fixture)
    assert every_semantic_record_resolves_provenance(indexed_fixture)
    assert report_has_all_required_sections(indexed_fixture)
```

Run: `uv run pytest tests/test_phase2_golden.py -q`  
Expected: FAIL until the fixture and checked-in golden snapshot match.

- [ ] **Step 2: Generate and inspect the golden snapshot**

Index the fixture twice with fixed observation time and compare all semantic JSONL files, the manifest semantic digests, capabilities JSON, and report bytes. Copy the inspected expected files into `tests/fixtures/golden/phase2/` using `apply_patch`; do not teach the test to rewrite its own golden data.

- [ ] **Step 3: Update the skill workflow and public documentation**

Document this agent sequence in `SKILL.md` and `references/agent-usage.md`: call capabilities, check memory status, request `.architecture-graph/` ignore permission when required, index, inspect terms, traverse high-navigation neighbors, query decisions by the appropriate independent score, fetch evidence/explanations, then report. State that prose and text-native diagrams work without JSON and that images, review mutation, history, and diff remain unavailable. Add concise command examples and update `README.md` and `agents/openai.yaml` to match.

- [ ] **Step 4: Run offline, deterministic, and full regression checks**

Run:

```bash
uv run pytest tests/test_phase2_golden.py -q
uv run pytest -q
uv build
git diff --check
```

Expected: golden tests PASS, full suite PASS, wheel and source distribution build, and `git diff --check` prints nothing. During the golden network test, monkeypatch socket connection and URL-opening APIs to raise so any attempted network access fails the suite.

- [ ] **Step 5: Verify installed artifacts and commit**

Install the built wheel into a temporary virtual environment, run `architecture-graph --version`, `architecture-graph capabilities --json`, index the mixed fixture, and run all six semantic read commands. Confirm packaged JSON resources load outside the checkout.

```bash
git add SKILL.md README.md references/agent-usage.md agents/openai.yaml tests/fixtures tests/test_phase2_golden.py
git commit -m "docs: complete Phase 2 evidence graph workflow"
```

## Completion Criteria

- A corpus containing prose and text-native diagrams, with no YAML or JSON, yields useful terms, claims, graph nodes, graph edges, rankings, decisions, explanations, and report assertions.
- `terms` and `neighbors` let an agent choose bounded evidence before reading broad source files.
- A graph hub can rank high for navigation and low for criticality; a low-degree hard constraint can rank high for criticality.
- Every semantic output resolves to exact source evidence and a persisted derivation.
- Duplicate bytes cannot inflate semantic breadth or scores.
- All seven advertised Phase 2 commands work against one immutable snapshot and enforce bounds.
- Identical inputs and rules produce byte-identical semantic output without network access or a downloaded model.
- Phase 1 commands and snapshots remain compatible.
