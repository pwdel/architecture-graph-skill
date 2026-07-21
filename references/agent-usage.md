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

Phase 2 supports prose, Markdown ADRs, plaintext, Mermaid, PlantUML, YAML, and
JSON through one semantic model. It does not interpret images. Capabilities
also report review mutation, decision lineage, and semantic diff as unavailable.
