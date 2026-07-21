# Architecture Graph Agent Usage

## Phase 1 Commands

```bash
architecture-graph memory status PATH [PATH ...] --json
architecture-graph index PATH [PATH ...] --json
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

Phase 1 exposes source-backed evidence only. Do not describe its records as a
semantic decision analysis. Phase 2 owns decision reduction and graph reports.
