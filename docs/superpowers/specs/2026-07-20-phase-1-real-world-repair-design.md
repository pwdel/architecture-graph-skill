# Architecture Graph Phase 1 Real-World Repair Design

**Date:** 2026-07-20  
**Branch:** `fix/real-world-scan-feedback`  
**Target release:** post-`v0.1.0`

## Problem

Release `v0.1.0` advertises this Phase 1 workflow in `SKILL.md` and
`references/agent-usage.md`:

```bash
architecture-graph memory status .
architecture-graph index .
architecture-graph get sources <source-id>
architecture-graph find segments --contains OrderPlaced
```

The released CLI implements only `index`. A real run against a 73 KB
`design-plan.json` failed first because `memory status` did not exist, then
because `index` tried to write under `~/.codex/memories`, outside the active
workspace sandbox. The CLI reduced that failure to `(PermissionError)`, so the
agent could not identify the path or suggest a useful recovery.

Phase 1 also accepts one directory as its root. Users need to scan one file, a
focused directory, an entire repository, or a set of paths without building a
configuration file first.

## Scope

Complete and extend the advertised Phase 1 contract:

- implement read-only `memory status`;
- implement bounded `get` and `find` queries;
- accept one or more file and directory inputs;
- store corpus memory inside the writable repository workspace;
- prevent generated memory from dirtying or contaminating the repository;
- return actionable human and machine errors; and
- lock the installed-skill workflow with realistic tests.

Phase 2 remains out of scope. This repair does not add term discovery, claim or
decision reduction, graph ranking, engineer reports, context packs, or semantic
diffs.

## Command Contract

### Index and status

```bash
architecture-graph index PATH [PATH ...] [--config PATH] [--json]
architecture-graph memory status PATH [PATH ...] [--config PATH] [--json]
```

Each positional input may name a supported file or a directory. Every input in
one invocation must resolve inside the same Git worktree. The resolver rejects
an input outside that worktree and rejects sets that span repositories.

The resolver normalizes paths without following a path outside the worktree,
sorts them by repository-relative path, and removes duplicates. When a selected
directory contains a selected descendant, the resolver retains the directory
and removes the redundant descendant. An explicit supported file bypasses the
default directory include globs. A selected directory continues to use the
existing configuration and source-selection rules.

Both commands return a stable `corpus_id`. `index --json` also returns the
published `snapshot_id`, observation ID, source and segment counts, warning
count, and reuse status. `memory status` returns `missing`, `fresh`, or `stale`
without creating a directory, lock, ledger, or pointer.

### Exact and bounded queries

```bash
architecture-graph get TYPE ID --repo ROOT [--corpus ID] [--snapshot ID]
architecture-graph find TYPE --repo ROOT [--corpus ID] [--snapshot ID]
```

`get` supports field projection and a character budget. `find` supports exact
field filters, text containment, field projection, result limits, a character
budget, stable cursors, and an optional JMESPath predicate over the bounded
page. The query envelope contains `items`, `truncated`, `omitted_count`, and
`cursor`.

Callers may omit `--corpus` when the repository has one corpus. If several
corpora exist, the CLI lists their IDs and selected input paths in an ambiguity
error. Callers can pin an immutable snapshot with `--snapshot`.

## Corpus Identity and Storage

The default memory root is:

```text
<git-worktree-root>/.architecture-graph/
```

The existing `--memory-root` option overrides that location. The
`ARCHITECTURE_GRAPH_MEMORY_ROOT` environment variable remains a lower-priority
override for users who have granted access to a central memory directory.

The repository memory layout is:

```text
.architecture-graph/
  corpora/
    <corpus-id>/
      CORPUS.json
      current.json
      observations.jsonl
      snapshots/
      reviews/
      cache/
```

`corpus_id` derives from the normalized repository identity, normalized selected
inputs, and selection-affecting configuration identity. File content does not
enter `corpus_id`; content changes make the existing corpus stale and produce a
new snapshot. A different input set produces a different corpus, so a focused
`lib/design` scan cannot replace the current pointer for a full-repository scan.

`CORPUS.json` records the schema version, corpus ID, repository identity, and
normalized input paths. The indexer validates it before reading or publishing
corpus state.

## Git-Ignore Preflight

Before the first write to the default project-local memory root, `index` asks
Git whether `.architecture-graph/` is ignored. If Git would track the
directory, the command exits before creating memory and tells the agent to ask
the user for permission to add this line to the repository's `.gitignore`:

```gitignore
.architecture-graph/
```

The CLI does not edit `.gitignore`, `.git/info/exclude`, or repository metadata.
After the user approves and adds the ignore rule, indexing can proceed. Source
discovery and Git dirty-state capture exclude the memory directory as a second
defense against recursive ingestion and observation drift.

`memory status` performs the same check for the default location as a read-only
diagnostic. A missing, unignored memory location reports `missing` plus the
required ignore rule; it does not fail or write. Explicit and environment-based
memory roots do not require a repository ignore rule because they may live
outside the worktree.

## Data Flow

1. Resolve the shared Git worktree and normalize the selected inputs.
2. Derive `corpus_id` and the corpus paths without touching the filesystem.
3. For `status`, inspect existing state and selected inputs without mutation.
4. For `index`, pass the ignore preflight before acquiring a corpus lock.
5. Expand directory inputs and admit explicit supported files.
6. Deduplicate sources and run the existing deterministic ingestion pipeline.
7. Publish an immutable snapshot and update only that corpus's observation
   ledger and current pointer.
8. Open the selected corpus and snapshot for bounded `get` and `find` reads.

The existing source, segment, evidence, derivation, warning, snapshot, and
observation record schemas remain unchanged. Corpus metadata lives in
`CORPUS.json` and command envelopes. Phase 1 preserves deterministic provenance
and keeps runtime observation facts out of semantic content digests.

## Errors

Human mode writes one concise diagnostic to stderr. JSON mode writes a stable
error object to stderr with these fields:

```json
{
  "error": {
    "code": "memory_not_ignored",
    "message": "Add .architecture-graph/ to the repository .gitignore and retry.",
    "path": ".architecture-graph/"
  }
}
```

The CLI defines distinct codes for unsupported inputs, paths outside the shared
worktree, cross-repository input sets, missing memory, ambiguous corpus
selection, missing records, stale or mismatched cursors, invalid configuration,
snapshot-integrity failures, publication conflicts, and filesystem failures.

Filesystem diagnostics name the attempted operation and a repository-relative
path when possible. They do not expose unrelated home-directory details. The
CLI catches expected user and operating-system failures but lets programming
faults surface during development.

## Backward Compatibility

`architecture-graph index <directory>` remains valid. Existing callers that set
`--memory-root` retain their storage location. The implementation recognizes
the existing single-project memory layout only when callers select it through
an explicit legacy `--memory-root`; new default writes use the corpus layout.

The skill instructions list only commands present in `architecture-graph
--help`. The README distinguishes the completed Phase 1 query surface from
deferred Phase 2 analysis.

## Tests and Acceptance

Automated tests cover:

- one explicit JSON file outside conventional architecture paths;
- one focused directory such as `lib/design`;
- a full repository;
- several files and directories with overlap and deduplication;
- rejection of paths outside one worktree and paths spanning repositories;
- stable corpus identity across input order and content changes;
- distinct corpus identity for different input sets;
- ignore preflight with zero writes on failure;
- recursive memory exclusion from sources and Git observations;
- read-only `missing`, `fresh`, and `stale` status;
- exact reads, projections, bounds, pagination, cursors, and JMESPath filtering;
- automatic corpus selection and actionable ambiguity errors;
- human and JSON error contracts, including useful permission diagnostics;
- pointer and ledger preservation for failed publication;
- wrapper execution from an installed copy; and
- every command shown in `SKILL.md` and `references/agent-usage.md`.

A regression fixture modeled on the reported `design-plan.json` run must prove
that an agent can index a large structured design file, inspect status, find
bounded segments, and retrieve cited records without opening the full generated
snapshot. The fixture may shrink repeated content while preserving nested
objects, arrays, decisions, workstreams, risks, questions, and source pointers.

The repair is complete when the full test suite, CLI help checks, package build,
skill validation, and installed-wrapper smoke test pass from a clean checkout.
Documentation cannot advertise a command absent from CLI help.
