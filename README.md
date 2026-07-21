# Architecture Graph Skill

Deterministic-first Codex skill for turning architecture documents into an evidence-backed memory of design commitments.

This repo is the architecture counterpart to `codebase-graph-skill`. Where a codebase graph helps an agent navigate source code, this skill helps an agent navigate ADRs, architecture notes, diagrams, and structured design records without treating every sentence as equally important.

The core idea is defensive: expose the decisions, constraints, missing rationale, and over-specified parts that engineers should discuss with an architect before implementation hardens around accidental detail.

## What It Does Today

The current implementation includes Phase 1 indexing and Phase 2 deterministic analysis. It can:

- discover architecture sources from a repository
- ingest Markdown ADRs and architecture notes
- extract Mermaid and PlantUML diagram evidence
- ingest selected YAML, JSON, and plaintext sources
- preserve source, segment, warning, observation, lineage, and snapshot records as JSONL
- publish immutable, content-addressed snapshots
- track Git observation metadata without putting runtime observation data into semantic content digests
- preserve deterministic provenance for derived records
- accept one file, one directory, a repository, or several same-repository paths
- keep separate corpus snapshots under project-local ignored memory
- inspect freshness and query indexed records with bounded output
- discover architecture vocabulary with sparse TF-IDF and glossary signals
- extract qualified claims from prose, Mermaid, and PlantUML
- build and traverse a typed evidence graph
- rank navigation, criticality, review priority, and extraction confidence independently
- reduce source-anchored decisions and render evidence-linked reports
- rank the complete selected corpus while returning compact, context-bounded views
- reconstruct decision objects from prose, ADRs, JSON, and YAML sibling fields
- separate concise report assertions from paginated evidence appendices

The command surface is:

```bash
architecture-graph memory status PATH [PATH ...] --json
architecture-graph index PATH [PATH ...] --json
architecture-graph find segments --repo ROOT --corpus CORPUS_ID --json
architecture-graph get sources SOURCE_ID --repo ROOT --corpus CORPUS_ID --json
architecture-graph capabilities --json
architecture-graph terms ROOT --corpus CORPUS_ID --json
architecture-graph neighbors ROOT --corpus CORPUS_ID --node NODE_ID --depth 2 --json
architecture-graph decisions ROOT --corpus CORPUS_ID --score criticality --json
architecture-graph evidence ROOT --corpus CORPUS_ID --for RECORD_ID --json
architecture-graph explain ROOT --corpus CORPUS_ID --id RECORD_ID --json
architecture-graph report ROOT --corpus CORPUS_ID
```

Phase 2 does not interpret raster images and does not include review mutation,
decision lineage, or semantic snapshot diff.

## Why This Exists

Architecture documents are not just text. They contain decisions with different levels of authority, status, scope, modality, and provenance:

- an accepted ADR should not be weighted like a draft note
- a `must` constraint should not be weighted like a possible option
- a diagram edge should be traceable as diagram-derived evidence
- an LLM proposal should not silently become an accepted commitment
- a highly connected term is not automatically a critical decision

The skill keeps those distinctions explicit. Deterministic extraction comes first. LLM-derived enrichment can be layered later, but it must be tagged separately from deterministic and human-derived records.

## Design Direction

The intended architecture pipeline is:

1. Build a corpus from ADRs, architecture docs, diagrams, and configured text/structured files.
2. Discover important terms with traditional NLP such as TF-IDF, headings, glossary signals, acronyms, and repeated architectural nouns.
3. Extract deterministic subject-verb-object and diagram relations with rule-based parsers.
4. Normalize relations into claims with modality, polarity, scope, status, and provenance.
5. Build typed graphs over claims, terms, entities, evidence, and source records.
6. Rank graph navigation with explainable structural and lexical features.
7. Reduce claims into candidate architecture decisions and rank consequence, review priority, and extraction confidence independently.
8. Produce human-readable engineer reports that cite source evidence and raise focused questions for architects.

The ranking model is deliberately not just "important nouns with many edges." Terms help find architecture vocabulary. Claims and decisions are the primary units of review.

Analysis and presentation have separate limits. Indexing extracts and ranks all
eligible records in the selected corpus. Query `--limit` and `--max-chars`
options only bound the returned projection; they never change persisted scores
or ordering. List commands return compact records with evidence counts and
representative evidence IDs. Use `get`, `evidence`, and `explain` for complete
records, paginated provenance, and independent feature vectors.

The default report uses at most two representative citations per assertion and
links each assertion to an evidence appendix ID. This keeps the report useful
for orientation without discarding the complete source-backed ledger.

## Repository Layout

```text
SKILL.md                         Agent-facing skill contract
bin/architecture-graph           Executable wrapper
scripts/architecture_graph/      Python implementation
references/agent-usage.md        Agent command and failure guidance
docs/superpowers/specs/          Design note
docs/superpowers/plans/          Phase implementation plans
tests/                           Unit and integration tests
```

## Install

This project targets Python 3.12.

```bash
uv sync
```

Run the CLI through `uv`:

```bash
uv run architecture-graph --help
```

Or use the checked-in wrapper from the repo:

```bash
./bin/architecture-graph --help
```

## Usage

Index a repository containing architecture material:

```bash
uv run architecture-graph index /path/to/repo --json
```

Before the first default index, add `.architecture-graph/` to the repository's
`.gitignore`. The CLI checks this rule before writing and never edits ignore
files itself. Use `--memory-root` for an explicitly managed external location.

By default, the indexer looks for files under common architecture and ADR paths:

```text
adr/**
architecture/**
docs/adr/**
docs/architecture/**
```

You can configure source selection with `.architecture-graph.yaml`:

```yaml
schema_version: 1
include:
  - docs/adr/**/*.md
  - docs/architecture/**/*
  - architecture/**/*
exclude:
  - "**/.git/**"
  - "**/node_modules/**"
plaintext:
  - docs/architecture/**/*.txt
source_roles:
  docs/adr/**/*.md: adr
  docs/architecture/**/*: architecture
source_authorities:
  docs/adr/**/*.md: accepted_adr_or_active_standard
  docs/architecture/**/*: maintained_architecture
aliases:
  pg: postgresql
max_segment_chars: 8000
spacy_model: en_core_web_sm
```

Snapshots are stored as flat JSONL files. There is no database requirement.

## Development

Run tests:

```bash
uv run pytest
```

Run a focused smoke index against the fixture repo:

```bash
uv run architecture-graph index tests/fixtures/phase1_repo --json
```

## Current Status

Version 0.3.1 provides deterministic prose-first evidence graphs with complete-corpus ranking and bounded evidence retrieval. JSON and YAML
contribute structure but are optional. The next increments may add human review
and semantic history; image interpretation remains outside the current scope.
