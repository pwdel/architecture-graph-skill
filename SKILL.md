---
name: architecture-graph
description: Build, query, and maintain evidence-backed architecture decision memories from ADRs, architecture notes, Mermaid, PlantUML, YAML, JSON, and selected text files. Use when Codex needs to identify critical design commitments, trace architecture claims to sources, find missing rationale or scope, compare architecture revisions, or prepare focused questions for an architect without loading the full corpus.
---

# Architecture Graph

## Workflow

1. Resolve `SKILL_DIR` as the directory containing this file.
2. Inspect the implemented command surface. Do not probe commands listed as unavailable:

```bash
"$SKILL_DIR/bin/architecture-graph" capabilities --json
```

3. Check memory without mutating it. Pass one file, one directory, or several
paths from the same Git worktree:

```bash
"$SKILL_DIR/bin/architecture-graph" memory status PATH [PATH ...] --json
```

4. If status returns `required_ignore`, ask the user before adding
`.architecture-graph/` to the repository `.gitignore`. Then index missing or
stale memory:

```bash
"$SKILL_DIR/bin/architecture-graph" index PATH [PATH ...] --json
```

5. Capture `corpus_id` from the result. Discover terms and traverse the graph
before opening broad source files:

```bash
"$SKILL_DIR/bin/architecture-graph" terms ROOT --corpus CORPUS_ID \
  --limit 20 --max-chars 12000 --json
"$SKILL_DIR/bin/architecture-graph" neighbors ROOT --corpus CORPUS_ID \
  --node NODE_ID --depth 2 --limit 20 --max-chars 12000 --json
"$SKILL_DIR/bin/architecture-graph" decisions ROOT --corpus CORPUS_ID \
  --score criticality --limit 20 --max-chars 12000 --json
"$SKILL_DIR/bin/architecture-graph" evidence ROOT --corpus CORPUS_ID \
  --for RECORD_ID --limit 10 --json
"$SKILL_DIR/bin/architecture-graph" explain ROOT --corpus CORPUS_ID \
  --id RECORD_ID --json
"$SKILL_DIR/bin/architecture-graph" report ROOT --corpus CORPUS_ID

# Phase 1 fallback and exact-record access
"$SKILL_DIR/bin/architecture-graph" find segments --repo ROOT \
  --corpus CORPUS_ID --contains TERM --limit 20 --max-chars 12000 --json
"$SKILL_DIR/bin/architecture-graph" get sources SOURCE_ID --repo ROOT \
  --corpus CORPUS_ID --fields id,path,parse_status --json
```

Indexing analyzes and ranks the complete selected corpus. Query `--limit` and
`--max-chars` values constrain only compact response projections. List results
include evidence counts and representative evidence IDs; use `get`, `evidence`,
and `explain` for full records, paginated provenance, and score feature vectors.

Reports are concise by default and expose stable appendix assertion IDs. Pass
an assertion ID to `evidence --for` to retrieve its complete evidence ledger.
Decision rankings keep navigation, criticality, review priority, extraction
confidence, corroboration, and completeness independent.

Phase 2 analyzes prose and text-native diagrams without requiring JSON. Raster
images, review mutation, decision lineage, and semantic snapshot diff are not
implemented.

## Trust Rules

- Treat deterministic, LLM, and human origins as separate fields. Phase 2 emits deterministic records only.
- Require source evidence for every architecture assertion.
- Treat navigation, extraction confidence, corroboration, completeness, criticality, and review priority as independent dimensions.
- Do not promote an unaccepted proposal into current commitments.
- Keep generated snapshots separate from the human review ledger.
- Open full source files only for the small evidence set returned by bounded commands.

## Reference

Read `references/agent-usage.md` for command envelopes, limits, and failure interpretation.
