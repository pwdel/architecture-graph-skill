# Architecture Graph Agent Usage

## Capability-First Workflow

```bash
architecture-graph capabilities --json
architecture-graph memory status PATH [PATH ...] --json
architecture-graph index PATH [PATH ...] --json
architecture-graph terms ROOT --corpus CORPUS_ID --limit 20 --json
architecture-graph neighbors ROOT --corpus CORPUS_ID --node NODE_ID --depth 2 --limit 20 --json
architecture-graph decisions ROOT --corpus CORPUS_ID --score criticality --limit 20 --json
architecture-graph evidence ROOT --corpus CORPUS_ID --for RECORD_ID --json
architecture-graph explain ROOT --corpus CORPUS_ID --id RECORD_ID --json
architecture-graph report ROOT --corpus CORPUS_ID
architecture-graph rationale build ROOT --corpus CORPUS_ID --json
architecture-graph rationale status ROOT --corpus CORPUS_ID --json
architecture-graph rationale find ROOT --corpus CORPUS_ID --limit 20 --json

# Exact Phase 1 evidence access remains available
architecture-graph find segments --repo ROOT --corpus CORPUS_ID \
  --contains OrderPlaced --limit 20 --max-chars 12000 --json
architecture-graph get segments SEGMENT_ID --repo ROOT --corpus CORPUS_ID \
  --fields id,path,text --max-chars 12000 --json
```

Inputs may be supported files or directories. One invocation must stay inside
one Git worktree. Explicit files bypass conventional architecture-path globs.

Default memory lives at `<git-root>/.architecture-graph/`. Indexing writes
nothing until Git ignores `.architecture-graph/`. If status reports
`required_ignore`, ask the user before changing `.gitignore`.

Read commands return `items`, `truncated`, `omitted_count`, and `cursor`.
`memory status`, `get`, and `find` do not mutate memory. Exit code 2 means
invalid input or state. JSON mode writes a structured error envelope to stderr.

Use `terms` and navigation-ranked `neighbors` to select a bounded evidence area.
Use `criticality` for consequence, `review_priority` for gaps and conflicts,
and `extraction_confidence` for interpretation reliability. Centrality is a
navigation aid, not architectural importance.

Term and graph ranking always cover the complete selected corpus. `--limit` and
`--max-chars` constrain only the compact response. An empty `items` list means
there are no matches; oversized compact records fail explicitly instead of
returning a non-progressing cursor.

The default `report` is intentionally concise. Each assertion includes at most
two citations, an evidence count, and an appendix assertion ID. Pass that ID to
`evidence --for ASSERTION_ID` to page the complete evidence ledger. Use
`explain --id RECORD_ID` for navigation, criticality, review priority,
extraction confidence, corroboration, and completeness feature vectors.

Rationale overlays are explicit, deterministic enrichments bound to one exact
base snapshot. Build one after indexing, inspect aggregate coverage with
`rationale status`, and page compact resolutions with `rationale find`. The
cursor is bound to the overlay ID, base snapshot, filter, limit, and projection.
Structured decision-local `rationale`, `context`, `reason`, `reasons`,
`justification`, and `why` fields are eligible. Explicit Markdown/ADR rationale
sections are eligible when they can be assigned to one decision without broad
co-occurrence inference. Document-level `why_now` is not decision rationale.

Composed decision views retain `base_diagnostics`, expose
`resolved_diagnostics`, and calculate `active_diagnostics`. Use `--base-only`
on `decisions`, `explain`, or `report` for the original v0.3.1 interpretation.
An incompatible or stale overlay fails explicitly; it is never silently
applied or discarded.

Phase 2 supports prose, Markdown ADRs, plaintext, Mermaid, PlantUML, YAML, and
JSON through one semantic model. It does not interpret images. Capabilities
also report review mutation, decision lineage, and semantic diff as unavailable.
