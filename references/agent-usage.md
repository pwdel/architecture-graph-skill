# Architecture Graph Agent Usage

## Phase 1 Commands

```bash
architecture-graph memory status . --json
architecture-graph index . --json
architecture-graph get sources <source-id> --json
architecture-graph get segments <segment-id> --fields id,path,text --json
architecture-graph find segments --contains OrderPlaced --limit 20 --max-chars 12000 --json
```

Read commands return complete JSON objects with `items`, `truncated`, `omitted_count`, and `cursor`. Exit code 2 means missing or invalid project state. Indexing never installs or downloads a parser. Phase 1 parser failures are persisted warnings; Phase 2 defines the optional statistical-model contract.
