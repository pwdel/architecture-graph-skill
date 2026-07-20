---
name: architecture-graph
description: Build, query, and maintain evidence-backed architecture decision memories from ADRs, architecture notes, Mermaid, PlantUML, YAML, JSON, and selected text files. Use when Codex needs to identify critical design commitments, trace architecture claims to sources, find missing rationale or scope, compare architecture revisions, or prepare focused questions for an architect without loading the full corpus.
---

# Architecture Graph

## Workflow

1. Resolve `SKILL_DIR` as the directory containing this file.
2. Check memory without mutating it:

```bash
"$SKILL_DIR/bin/architecture-graph" memory status .
```

3. If selected sources or pipeline inputs changed, index them:

```bash
"$SKILL_DIR/bin/architecture-graph" index .
```

4. Use bounded `get` and `find` commands before opening broad source files. Phase 2 adds decision, graph, evidence, explanation, context, report, and diff commands.

## Trust Rules

- Treat deterministic, LLM, and human origins as separate fields.
- Require source evidence for every architecture assertion.
- Treat extraction confidence, human review status, criticality, and review priority as independent dimensions.
- Do not promote an unaccepted proposal into current commitments.
- Keep generated snapshots separate from the human review ledger.
- Open full source files only for the small evidence set returned by bounded commands.

## Reference

Read `references/agent-usage.md` for command envelopes, limits, and failure interpretation.
