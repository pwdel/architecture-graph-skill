---
name: architecture-graph
description: Build, query, and maintain evidence-backed architecture decision memories from ADRs, architecture notes, Mermaid, PlantUML, YAML, JSON, and selected text files. Use when Codex needs to identify critical design commitments, trace architecture claims to sources, find missing rationale or scope, compare architecture revisions, or prepare focused questions for an architect without loading the full corpus.
---

# Architecture Graph

## Workflow

1. Resolve `SKILL_DIR` as the directory containing this file.
2. Check memory without mutating it. Pass one file, one directory, or several
paths from the same Git worktree:

```bash
"$SKILL_DIR/bin/architecture-graph" memory status PATH [PATH ...] --json
```

3. If status returns `required_ignore`, ask the user before adding
`.architecture-graph/` to the repository `.gitignore`. Then index missing or
stale memory:

```bash
"$SKILL_DIR/bin/architecture-graph" index PATH [PATH ...] --json
```

4. Capture `corpus_id` from the result. Use bounded queries before opening
broad source files:

```bash
"$SKILL_DIR/bin/architecture-graph" find segments --repo ROOT \
  --corpus CORPUS_ID --contains TERM --limit 20 --max-chars 12000 --json
"$SKILL_DIR/bin/architecture-graph" get sources SOURCE_ID --repo ROOT \
  --corpus CORPUS_ID --fields id,path,parse_status --json
```

Phase 1 returns indexed evidence. It does not synthesize architecture decisions.
Phase 2 adds decision, graph, explanation, report, context, and diff commands.

## Trust Rules

- Treat deterministic, LLM, and human origins as separate fields.
- Require source evidence for every architecture assertion.
- Treat extraction confidence, human review status, criticality, and review priority as independent dimensions.
- Do not promote an unaccepted proposal into current commitments.
- Keep generated snapshots separate from the human review ledger.
- Open full source files only for the small evidence set returned by bounded commands.

## Reference

Read `references/agent-usage.md` for command envelopes, limits, and failure interpretation.
