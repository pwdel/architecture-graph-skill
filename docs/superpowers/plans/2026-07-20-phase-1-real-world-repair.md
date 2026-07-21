# Architecture Graph Phase 1 Real-World Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the advertised Phase 1 workflow work for one file, one directory, a repository, or several same-repository paths with writable corpus-scoped memory and bounded read commands.

**Architecture:** Resolve user inputs into an immutable `CorpusSelection` before source discovery. Store each selection under `<repo>/.architecture-graph/corpora/<corpus-id>` by default, retain explicit external memory roots, and reuse the existing snapshot publisher inside each corpus. Add a read-only query layer over validated snapshot JSONL and expose it through `memory status`, `get`, and `find` with stable envelopes and errors.

**Tech Stack:** Python 3.12.13, argparse, pathlib, subprocess/Git, JSON/JSONL, JMESPath, PyYAML, pytest, uv

## Global Constraints

- Keep Phase 2 term, claim, decision, graph, report, context-pack, and diff behavior out of scope.
- Require every input in one corpus to resolve inside one Git worktree.
- Default memory to `<git-worktree-root>/.architecture-graph/` and write nothing until Git ignores that directory.
- Preserve `--memory-root` and `ARCHITECTURE_GRAPH_MEMORY_ROOT`; explicit CLI value wins over the environment, which wins over the project-local default.
- Keep `memory status`, `get`, and `find` read-only.
- Keep existing Phase 1 record schemas unchanged; store corpus metadata in `CORPUS.json` and command envelopes.
- Keep query output bounded and include `items`, `truncated`, `omitted_count`, and `cursor`.
- Preserve snapshot and observation failure atomicity.
- Do not edit `.gitignore`, `.git/info/exclude`, or Git metadata from the CLI.

---

### Task 1: Resolve Same-Repository Corpus Inputs

**Files:**
- Create: `scripts/architecture_graph/corpus.py`
- Create: `tests/test_corpus.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `CorpusSelection(repository: Path, inputs: tuple[str, ...], corpus_id: str)`.
- Produces: `resolve_corpus(paths: Sequence[Path], config_identity: str) -> CorpusSelection`.
- Produces: `find_git_worktree(path: Path) -> Path`.
- Consumes later: source discovery, project paths, status, and CLI indexing all use `CorpusSelection`.

- [ ] **Step 1: Add corpus fixtures and failing resolution tests**

Add a helper to `tests/conftest.py`:

```python
def ignore_architecture_graph(repo: Path) -> None:
    ignore = repo / ".gitignore"
    prior = ignore.read_text() if ignore.exists() else ""
    if ".architecture-graph/\n" not in prior:
        ignore.write_text(prior + ".architecture-graph/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore architecture graph memory")
```

Create `tests/test_corpus.py` with tests that:

```python
from pathlib import Path

import pytest

from architecture_graph.canonical import sha256_digest
from architecture_graph.corpus import resolve_corpus


def test_corpus_normalizes_order_overlap_and_content_changes(
    architecture_repo: Path,
) -> None:
    directory = architecture_repo / "docs"
    file = directory / "adr" / "ADR-001.md"
    first = resolve_corpus([file, directory], "config:one")
    before = first.corpus_id
    file.write_text(file.read_text() + "\nChanged.\n")
    second = resolve_corpus([directory, file], "config:one")
    assert first.inputs == second.inputs == ("docs",)
    assert second.corpus_id == before


def test_corpus_identity_changes_with_inputs_and_config(
    architecture_repo: Path,
) -> None:
    file = architecture_repo / "docs" / "adr" / "ADR-001.md"
    by_file = resolve_corpus([file], "config:one")
    by_repo = resolve_corpus([architecture_repo], "config:one")
    changed_config = resolve_corpus([file], "config:two")
    assert len({by_file.corpus_id, by_repo.corpus_id, changed_config.corpus_id}) == 3


def test_corpus_rejects_cross_repository_and_outside_paths(
    architecture_repo: Path, tmp_path: Path
) -> None:
    second = tmp_path / "second"
    second.mkdir()
    # Initialize `second` with the existing `git` fixture helper.
    from conftest import git
    git(second, "init", "-b", "main")
    foreign = second / "architecture.json"
    foreign.write_text("{}")
    with pytest.raises(ValueError, match="same Git worktree"):
        resolve_corpus([architecture_repo, foreign], "config:one")
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run: `uv run pytest tests/test_corpus.py -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'architecture_graph.corpus'`.

- [ ] **Step 3: Implement corpus resolution**

Create `scripts/architecture_graph/corpus.py` with:

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess

from architecture_graph.canonical import canonical_bytes, sha256_digest
from architecture_graph.project import normalize_remote


@dataclass(frozen=True)
class CorpusSelection:
    repository: Path
    inputs: tuple[str, ...]
    corpus_id: str


def find_git_worktree(path: Path) -> Path:
    probe = path.resolve()
    cwd = probe if probe.is_dir() else probe.parent
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"input is not inside a Git worktree: {path}")
    return Path(result.stdout.strip()).resolve()


def _normalized_inputs(repository: Path, paths: Sequence[Path]) -> tuple[str, ...]:
    if not paths:
        raise ValueError("at least one corpus input is required")
    relative: list[str] = []
    for raw in paths:
        selected = raw.resolve()
        if not selected.exists():
            raise ValueError(f"corpus input does not exist: {raw}")
        if not selected.is_file() and not selected.is_dir():
            raise ValueError(f"corpus input is not a file or directory: {raw}")
        if find_git_worktree(selected) != repository:
            raise ValueError("all corpus inputs must belong to the same Git worktree")
        value = selected.relative_to(repository).as_posix() or "."
        relative.append(value)
    retained: list[str] = []
    for value in sorted(set(relative)):
        if any(
            parent == "." or value == parent or value.startswith(parent + "/")
            for parent in retained
        ):
            continue
        retained.append(value)
    return tuple(retained)


def resolve_corpus(
    paths: Sequence[Path], config_identity: str
) -> CorpusSelection:
    if not paths:
        raise ValueError("at least one corpus input is required")
    repository = find_git_worktree(paths[0])
    inputs = _normalized_inputs(repository, paths)
    remote = subprocess.run(
        ["git", "-C", str(repository), "config", "--get", "remote.origin.url"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    digest = sha256_digest(
        canonical_bytes(
            {
                "schema_version": 1,
                "repository": {
                    "remote": normalize_remote(remote),
                    "worktree": repository.as_posix(),
                },
                "inputs": list(inputs),
                "config_identity": config_identity,
            }
        )
    )
    return CorpusSelection(repository, inputs, digest.removeprefix("sha256:"))
```

Remove the unused `sha256_digest` import from the test if lint or the final review reports it.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_corpus.py tests/test_sources.py::test_remote_normalization_removes_transport_spelling_noise -v`

Expected: PASS.

- [ ] **Step 5: Commit corpus resolution**

```bash
git add scripts/architecture_graph/corpus.py tests/test_corpus.py tests/conftest.py
git commit -m "feat: resolve architecture corpora"
```

---

### Task 2: Select Explicit Files and Focused Directories

**Files:**
- Modify: `scripts/architecture_graph/sources.py`
- Modify: `scripts/architecture_graph/indexer.py`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Consumes: `CorpusSelection.inputs` as normalized repository-relative paths.
- Produces: `discover_sources(root: Path, config: ProjectConfig, selected_paths: Sequence[str] = (".",)) -> list[SourceInput]`.
- Produces: `capture_repository(selection: CorpusSelection, config_path: Path | None, observed_at: str | None) -> RepositoryCapture` through renamed internal capture helpers.

- [ ] **Step 1: Add failing source-selection tests**

Append to `tests/test_sources.py`:

```python
def test_explicit_supported_file_bypasses_default_include(
    architecture_repo: Path,
) -> None:
    plan = architecture_repo / "lib" / "design" / "design-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text('{"decision":"backend owns truth"}')
    from conftest import git
    git(architecture_repo, "add", "lib/design/design-plan.json")
    git(architecture_repo, "commit", "-m", "add design plan")
    selected = discover_sources(
        architecture_repo, ProjectConfig(), ("lib/design/design-plan.json",)
    )
    assert [item.relative_path for item in selected] == [
        "lib/design/design-plan.json"
    ]


def test_focused_directory_applies_format_rules_and_deduplicates(
    architecture_repo: Path,
) -> None:
    selected = discover_sources(
        architecture_repo, ProjectConfig(), ("docs", "docs/adr/ADR-001.md")
    )
    assert [item.relative_path for item in selected] == ["docs/adr/ADR-001.md"]


def test_explicit_unsupported_file_fails(architecture_repo: Path) -> None:
    readme = architecture_repo / "README.bin"
    readme.write_bytes(b"binary")
    with pytest.raises(ValueError, match="unsupported explicit source"):
        discover_sources(architecture_repo, ProjectConfig(), ("README.bin",))
```

- [ ] **Step 2: Verify old discovery ignores explicit selections**

Run: `uv run pytest tests/test_sources.py -k 'explicit_supported or focused_directory or explicit_unsupported' -v`

Expected: FAIL because `discover_sources` accepts only two arguments.

- [ ] **Step 3: Extend source discovery without changing record schemas**

In `sources.py`, add `selected_paths: Sequence[str] = (".",)` and classify each
selection before reading Git paths:

```python
def _inside_selection(path: str, selected: str) -> bool:
    return selected == "." or path == selected or path.startswith(selected + "/")


def discover_sources(
    root: Path,
    config: ProjectConfig,
    selected_paths: Sequence[str] = (".",),
) -> list[SourceInput]:
    tracked = sorted(
        item.decode("utf-8")
        for item in _git_bytes(root, "ls-files", "-z").split(b"\0")
        if item
    )
    tracked_set = set(tracked)
    explicit_files = {
        value for value in selected_paths if value != "." and (root / value).is_file()
    }
    for value in explicit_files:
        if _kind(value) == "unsupported":
            raise ValueError(f"unsupported explicit source: {value}")
    selected = {
        path: True
        for path in tracked
        if (root / path).is_file()
        and any(_inside_selection(path, value) for value in selected_paths)
        and (path in explicit_files or path_matches(path, config.include))
        and not path_matches(path, config.exclude)
        and _kind(path) != "unsupported"
        and (
            path in explicit_files
            or _kind(path) != "text"
            or path_matches(path, config.plaintext)
        )
    }
    # Retain the existing configured-untracked validation, but admit an
    # untracked explicit file and mark it `tracked=False`.
    for value in explicit_files:
        if value not in selected:
            selected[value] = value in tracked_set
    # Continue with the existing `_read_source` and role/authority loop.
```

Refactor the existing `config.untracked` loop into the indicated continuation;
do not duplicate its validation.

- [ ] **Step 4: Thread `CorpusSelection` through stable capture**

Change `_repository_capture`, `_stable_repository_capture`, and
`_prepublication_observation` in `indexer.py` to accept `selection`, use
`selection.repository` for Git/config operations, pass `selection.inputs` to
`discover_sources`, and include `corpus_id` plus selected inputs in the capture
token. Keep `RepositoryCapture` fields unchanged.

- [ ] **Step 5: Run source and indexing tests**

Run: `uv run pytest tests/test_sources.py tests/test_phase1_cli.py -v`

Expected: PASS after adapting existing direct `index_repository(root, ...)`
callers temporarily with `resolve_corpus((root,), config_identity)` inside
`index_repository`; Task 4 replaces that compatibility bridge.

- [ ] **Step 6: Commit selection support**

```bash
git add scripts/architecture_graph/sources.py scripts/architecture_graph/indexer.py tests/test_sources.py
git commit -m "feat: select explicit architecture inputs"
```

---

### Task 3: Add Corpus-Scoped Paths and Ignore Preflight

**Files:**
- Modify: `scripts/architecture_graph/project.py`
- Modify: `scripts/architecture_graph/corpus.py`
- Modify: `tests/test_corpus.py`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Produces: `ProjectPaths.resolve(selection: CorpusSelection, memory_root: Path | None = None) -> ProjectPaths`.
- Produces: `MemoryLocation(root: Path, requires_git_ignore: bool, legacy_project_dir: Path | None)`.
- Produces: `resolve_memory_location(selection, explicit_root) -> MemoryLocation`.
- Produces: `check_default_memory_ignored(selection) -> None`, raising `MemoryNotIgnoredError` before writes.
- Produces: `write_corpus_metadata(project, selection) -> None` and `validate_corpus_metadata(project, selection) -> None`.

- [ ] **Step 1: Add failing path, precedence, metadata, and ignore tests**

Add tests that assert:

```python
def test_default_memory_is_corpus_scoped_and_requires_ignore(
    architecture_repo: Path,
) -> None:
    selection = resolve_corpus([architecture_repo], "config:one")
    with pytest.raises(MemoryNotIgnoredError, match=".architecture-graph/"):
        check_default_memory_ignored(selection)
    assert not (architecture_repo / ".architecture-graph").exists()


def test_ignored_default_and_explicit_memory_precedence(
    architecture_repo: Path, tmp_path: Path, monkeypatch
) -> None:
    from conftest import ignore_architecture_graph
    ignore_architecture_graph(architecture_repo)
    selection = resolve_corpus([architecture_repo], "config:one")
    default = ProjectPaths.resolve(selection)
    assert default.project_dir == (
        architecture_repo / ".architecture-graph" / "corpora" / selection.corpus_id
    )
    monkeypatch.setenv("ARCHITECTURE_GRAPH_MEMORY_ROOT", str(tmp_path / "env"))
    assert ProjectPaths.resolve(selection).projects_root == tmp_path / "env" / "corpora"
    assert ProjectPaths.resolve(selection, tmp_path / "cli").projects_root == tmp_path / "cli" / "corpora"
```

Add a round-trip test for `CORPUS.json` and a mismatch test that preserves its
bytes and fails before snapshot publication.

- [ ] **Step 2: Run focused tests**

Run: `uv run pytest tests/test_corpus.py tests/test_sources.py::test_memory_root_precedence -v`

Expected: FAIL because corpus-scoped paths and ignore checks do not exist.

- [ ] **Step 3: Implement memory location and ignore checking**

In `corpus.py`, add:

```python
class MemoryNotIgnoredError(RuntimeError):
    pass


@dataclass(frozen=True)
class MemoryLocation:
    root: Path
    requires_git_ignore: bool
    legacy_project_dir: Path | None = None


def resolve_memory_location(
    selection: CorpusSelection, explicit_root: Path | None
) -> MemoryLocation:
    if explicit_root is not None:
        return MemoryLocation(explicit_root.resolve(), False)
    configured = os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT")
    if configured:
        return MemoryLocation(Path(configured).resolve(), False)
    return MemoryLocation(selection.repository / ".architecture-graph", True)


def check_default_memory_ignored(selection: CorpusSelection) -> None:
    result = subprocess.run(
        [
            "git", "-C", str(selection.repository), "check-ignore", "-q",
            ".architecture-graph/",
        ],
        check=False,
    )
    if result.returncode == 1:
        raise MemoryNotIgnoredError(
            "add .architecture-graph/ to the repository .gitignore and retry"
        )
    if result.returncode != 0:
        raise RuntimeError("Git check-ignore failed for .architecture-graph/")
```

Import `os`. Call the check only from the write path when
`requires_git_ignore` is true.

- [ ] **Step 4: Make `ProjectPaths` corpus-scoped**

Replace its root/project-id constructor inputs with `CorpusSelection`. Normalize
all new storage modes to `<memory-root>/corpora/<corpus-id>`. Set
`project_dir = projects_root / corpus_id`, add
`corpus_file = project_dir / "CORPUS.json"`, and retain existing snapshot,
review, cache, pointer, ledger, and lock names under that directory.

Write `CORPUS.json` with `atomic_write_json` after the ignore check and before
publication. Validate exact schema/version, corpus ID, repository identity, and
input paths on every existing corpus open.

For an explicit `--memory-root`, also check the `v0.1.0` path
`<memory-root>/<project-id>/current.json`. When that legacy pointer exists and
the selection is the repository root, set `legacy_project_dir` and open the old
layout without moving or rewriting it. Reject focused or multi-path selections
against that legacy layout with `legacy_memory_requires_repository_root`. Add
tests for read/reuse of the legacy root and for the focused-selection rejection.

- [ ] **Step 5: Exclude memory from dirty Git capture**

Update `_dirty_preimage_once` in `project.py` to ignore status entries whose
repository-relative path is `.architecture-graph` or starts with
`.architecture-graph/`. Add a test that creates ignored memory bytes and proves
`capture_git_observation(...)["dirty_fingerprint"]` does not change.

- [ ] **Step 6: Run focused regression tests**

Run: `uv run pytest tests/test_corpus.py tests/test_sources.py tests/test_snapshot.py -v`

Expected: PASS.

- [ ] **Step 7: Commit corpus storage**

```bash
git add scripts/architecture_graph/corpus.py scripts/architecture_graph/project.py tests/test_corpus.py tests/test_sources.py
git commit -m "feat: store corpus memory in repositories"
```

---

### Task 4: Integrate Corpus Identity with Indexing

**Files:**
- Modify: `scripts/architecture_graph/indexer.py`
- Modify: `scripts/architecture_graph/config.py`
- Modify: `tests/test_phase1_cli.py`
- Add fixture: `tests/fixtures/design_plan/design-plan.json`

**Interfaces:**
- Produces: `index_corpus(paths: Sequence[Path], memory_root: Path | None = None, config_path: Path | None = None, observed_at: str | None = None) -> IndexResult`.
- Keeps: `index_repository(root: Path, ...) -> IndexResult` as a compatibility wrapper around `index_corpus((root,), ...)`.
- Extends: `IndexResult.corpus_id: str` and its JSON envelope.

- [ ] **Step 1: Add a compact real-world design-plan fixture**

Create valid nested JSON with at least `title`, `status`, `target_state`, two
`boundaries`, two `workstreams`, accepted and proposed `decision_log` entries,
`open_questions`, `risks`, and two `source_context.source_documents`. Keep it
under 15 KB; repeat nested shapes rather than copying the user's project data.

- [ ] **Step 2: Add failing end-to-end indexing tests**

Add tests that copy the fixture into `lib/design/design-plan.json`, initialize a
Git repository, add `.architecture-graph/` to `.gitignore`, and assert:

```python
result = index_corpus((repo / "lib" / "design" / "design-plan.json",))
assert result.corpus_id
project = ProjectPaths.resolve(
    resolve_corpus(
        (repo / "lib" / "design" / "design-plan.json",),
        configuration_identity(repo, None),
    )
)
reader = SnapshotReader.open(project)
assert [source["path"] for source in reader.iter("sources")] == [
    "lib/design/design-plan.json"
]
assert any(
    segment["metadata"].get("json_pointer") == "/decision_log/0/status"
    for segment in reader.iter("segments")
)
```

Also test two corpora in one repository have separate `current.json` pointers,
and test the ignore failure leaves `.architecture-graph` absent.

- [ ] **Step 3: Run the new indexing tests**

Run: `uv run pytest tests/test_phase1_cli.py -k 'design_plan or two_corpora or ignore_preflight' -v`

Expected: FAIL because `index_corpus` and corpus IDs are missing.

- [ ] **Step 4: Expose stable configuration identity before corpus resolution**

Add to `config.py`:

```python
def configuration_identity(repository: Path, config_path: Path | None) -> str:
    selected, explicit = resolve_config_path(repository, config_path)
    text = _configuration_text(selected, explicit=explicit)
    return sha256_digest(
        canonical_bytes(
            {
                "path": selected.relative_to(repository).as_posix()
                if selected.is_relative_to(repository)
                else selected.as_posix(),
                "content": text,
            }
        )
    )
```

- [ ] **Step 5: Implement `index_corpus` and preserve the wrapper**

Resolve the repository from the first input, compute configuration identity,
resolve the corpus, resolve corpus paths, perform ignore and metadata preflight,
then run the existing capture/ingestion/publication flow. Add `corpus_id` to
`IndexResult` and every return site. Keep `index_repository` as:

```python
def index_repository(root: Path, **kwargs) -> IndexResult:
    return index_corpus((root,), **kwargs)
```

Use typed keyword parameters rather than an untyped production `**kwargs`; the
snippet only fixes delegation semantics.

- [ ] **Step 6: Run indexing and source suites**

Run: `uv run pytest tests/test_phase1_cli.py tests/test_sources.py tests/test_snapshot.py -v`

Expected: PASS.

- [ ] **Step 7: Commit indexing integration**

```bash
git add scripts/architecture_graph/config.py scripts/architecture_graph/indexer.py tests/test_phase1_cli.py tests/fixtures/design_plan/design-plan.json
git commit -m "feat: index corpus-scoped architecture inputs"
```

---

### Task 5: Implement Read-Only Status and Bounded Queries

**Files:**
- Create: `scripts/architecture_graph/query.py`
- Create: `tests/test_query.py`
- Modify: `scripts/architecture_graph/jsonl_store.py`

**Interfaces:**
- Produces: `QueryEnvelope(items: tuple[Record, ...], truncated: bool, omitted_count: int, cursor: str | None, max_chars: int)`.
- Produces: `memory_status(paths, memory_root=None, config_path=None, fields=None, max_chars=12000) -> QueryEnvelope`.
- Produces: `get_snapshot_record(reader, record_type, record_id, fields=None, max_chars=12000) -> QueryEnvelope`.
- Produces: `find_snapshot_records(reader, record_type, filters=None, contains=None, fields=None, limit=20, max_chars=12000, cursor=None, expression=None) -> QueryEnvelope`.
- Produces: `render_query_envelope(envelope, output_format) -> str`, including its terminal newline inside `max_chars`.

- [ ] **Step 1: Add failing status tests**

Test missing status with no `.architecture-graph` creation, fresh status after
indexing, stale status after changing selected JSON bytes, field projection
that retains mandatory `state`, and the unignored diagnostic fields
`required_ignore=".architecture-graph/"` and `writable=False`.

- [ ] **Step 2: Add failing get/find tests**

Index the design-plan fixture, select a source ID, and test exact get; JSON
pointer containment; field filters; `limit=1`; `max_chars`; omitted counts;
cursor continuation; stale/mismatched cursor rejection; and JMESPath applied
only to the already bounded page.

- [ ] **Step 3: Verify the query module is missing**

Run: `uv run pytest tests/test_query.py -v`

Expected: FAIL during collection with `ModuleNotFoundError`.

- [ ] **Step 4: Implement query envelopes and rendering**

Create `query.py` with a frozen `QueryEnvelope`, canonical cursor payloads bound
by a SHA-256 digest of snapshot ID, record type, filters, contains text,
fields, limit, and offset. Reject a cursor when any bound input changes. Render
canonical JSON or compact Markdown, always with one terminal newline. Remove
items from the end until serialized output fits; update `truncated`,
`omitted_count`, and cursor after each removal. Raise `ValueError` if metadata
alone exceeds `max_chars`.

- [ ] **Step 5: Implement read-only status**

Reuse corpus/config resolution without calling `mkdir`, acquiring
`ProjectLock`, writing metadata, repairing ledgers, or changing pointers. Return
one item with `state`, `fresh`, `corpus_id`, `snapshot_id`, `observation_id`,
`snapshot_kind`, `orphan_observation_count`, and ignore guidance. Reuse the
indexer's stable material capture to compare `material_input_digest`. Extract
`capture_material_state(selection, config_path) -> MaterialState` from
`indexer.py`; both `memory_status` and `index_corpus` must call that exact helper.

- [ ] **Step 6: Implement bounded JSONL scanning**

Extend `jsonl_store.py` with an iterator that accepts an offset and scans one
record file once. Keep exact reads on `SnapshotReader.get`. Project fields only
after filter and contains evaluation. Count all remaining matches when
calculating `omitted_count`; do not load unrelated record files.

- [ ] **Step 7: Run query and integrity suites**

Run: `uv run pytest tests/test_query.py tests/test_jsonl_store.py tests/test_snapshot.py -v`

Expected: PASS.

- [ ] **Step 8: Commit the query layer**

```bash
git add scripts/architecture_graph/query.py scripts/architecture_graph/jsonl_store.py tests/test_query.py
git commit -m "feat: query Phase 1 architecture memory"
```

---

### Task 6: Expose the Complete CLI and Actionable Errors

**Files:**
- Modify: `scripts/architecture_graph/cli.py`
- Create: `scripts/architecture_graph/errors.py`
- Modify: `tests/test_cli_smoke.py`
- Modify: `tests/test_phase1_cli.py`

**Interfaces:**
- Produces CLI: `index PATH [PATH ...]`, `memory status PATH [PATH ...]`, `get TYPE ID`, and `find TYPE`.
- Produces: `ArchitectureGraphError(code: str, message: str, path: str | None)` for expected user/state failures.
- Produces: human one-line stderr and `{"error":{"code","message","path"}}` JSON stderr.

- [ ] **Step 1: Add failing parser/help tests**

Assert top-level help lists `index`, `memory`, `get`, and `find`; each documented
help invocation exits zero; `index` and status accept multiple positional
paths; get/find accept `--repo`, `--corpus`, `--snapshot`, `--fields`, and
`--max-chars`; find also accepts repeated `--where`, `--contains`, `--limit`,
`--cursor`, and `--jmespath`.

- [ ] **Step 2: Add failing CLI workflow and error tests**

Drive `main()` through ignore failure, successful design-plan index, fresh
status, bounded find, exact get, and ambiguous corpus selection. Parameterize
human and JSON modes. Assert stdout stays empty on failure, stderr has one line
in human mode, JSON parses in machine mode, permission errors name the attempted
operation and repository-relative path, and pointer bytes survive failures.

- [ ] **Step 3: Run focused CLI tests**

Run: `uv run pytest tests/test_cli_smoke.py tests/test_phase1_cli.py -k 'help or workflow or error or permission' -v`

Expected: FAIL because the parser exposes only `index` and flattens `OSError`.

- [ ] **Step 4: Implement typed expected errors**

Create `errors.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureGraphError(RuntimeError):
    code: str
    message: str
    path: str | None = None

    def __str__(self) -> str:
        return self.message

    def as_json(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "path": self.path,
            }
        }
```

Map corpus, configuration, query, snapshot, publication, and filesystem
boundaries to stable codes near the boundary that has the needed context. Do
not catch `KeyboardInterrupt`, `MemoryError`, or unexpected programming faults.

- [ ] **Step 5: Implement parser and dispatch**

Build the command tree described in the spec. Parse comma-separated fields and
`KEY=VALUE` filters with dedicated helpers. For get/find, enumerate
`<memory-root>/corpora/*/CORPUS.json`; select the only corpus or require
`--corpus`. Open `SnapshotReader`, call query functions, and write the rendered
result directly so the query budget includes the terminal newline.

- [ ] **Step 6: Render errors consistently**

Add:

```python
def _print_error(error: ArchitectureGraphError, as_json: bool) -> None:
    if as_json:
        sys.stderr.write(canonical_dumps(error.as_json()) + "\n")
    else:
        suffix = "" if error.path is None else f" [{error.path}]"
        sys.stderr.write(f"architecture-graph: {error.message}{suffix}\n")
```

Wrap expected errors once around dispatch. Convert `OSError` at each operation
boundary so its code, operation, and sanitized path remain available.

- [ ] **Step 7: Run all CLI tests**

Run: `uv run pytest tests/test_cli_smoke.py tests/test_phase1_cli.py tests/test_query.py -v`

Expected: PASS.

- [ ] **Step 8: Commit the complete Phase 1 CLI**

```bash
git add scripts/architecture_graph/cli.py scripts/architecture_graph/errors.py tests/test_cli_smoke.py tests/test_phase1_cli.py
git commit -m "feat: complete Phase 1 command surface"
```

---

### Task 7: Align the Skill Contract and Validate Installation

**Files:**
- Modify: `SKILL.md`
- Modify: `references/agent-usage.md`
- Modify: `README.md`
- Modify: `agents/openai.yaml`
- Modify: `tests/test_cli_smoke.py`

**Interfaces:**
- Consumes: the completed CLI from Task 6.
- Produces: installed-skill instructions that use only implemented commands.
- Produces: archive-copy launcher recovery instructions that do not assume executable bits survive a GitHub ZIP download.

- [ ] **Step 1: Add documentation-contract and installed-copy tests**

Parse fenced `architecture-graph` commands from `SKILL.md` and
`references/agent-usage.md`, substitute fixture paths and IDs, and assert every
command name appears in top-level help. Copy the repository to a temporary
directory while clearing the launcher executable bit, run `uv sync --frozen`,
assert direct execution fails for the expected permission reason, apply the
documented `chmod +x bin/architecture-graph`, and assert `--version` and help
succeed.

- [ ] **Step 2: Run contract tests and confirm stale documentation**

Run: `uv run pytest tests/test_cli_smoke.py -k 'documented or installed_copy' -v`

Expected: FAIL until the docs and installer smoke contract match the CLI.

- [ ] **Step 3: Update skill instructions**

Make the workflow explicit:

```bash
architecture-graph memory status PATH [PATH ...] --json
# If status reports required_ignore, ask before adding it to .gitignore.
architecture-graph index PATH [PATH ...] --json
architecture-graph find segments --repo ROOT --corpus CORPUS_ID \
  --contains TERM --limit 20 --max-chars 12000 --json
architecture-graph get sources SOURCE_ID --repo ROOT \
  --corpus CORPUS_ID --fields id,path,parse_status --json
```

State that Phase 1 returns evidence records and does not synthesize architecture
decisions. Tell the agent to open only the bounded evidence returned by queries.

- [ ] **Step 4: Update README and agent metadata**

List the four completed commands and project-local memory preflight. Keep Phase
2 features under planned work. Regenerate `agents/openai.yaml` with:

```bash
/usr/bin/python3 /Users/patrick/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py . \
  --interface display_name="Architecture Graph" \
  --interface short_description="Index and query architecture evidence" \
  --interface default_prompt="Use $architecture-graph to index selected architecture files and return bounded, source-backed evidence."
```

- [ ] **Step 5: Run package, skill, and installed-wrapper validation**

Run:

```bash
uv run pytest -v
uv run python -m compileall -q scripts tests
uv build
/usr/bin/python3 /Users/patrick/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
./bin/architecture-graph --help
./bin/architecture-graph memory status --help
./bin/architecture-graph index --help
./bin/architecture-graph get --help
./bin/architecture-graph find --help
git diff --check
```

Expected: all commands exit zero; pytest passes; `uv build` creates wheel and
source distribution; skill validation prints `Skill is valid!`; diff check has
no output.

- [ ] **Step 6: Commit documentation and validation**

```bash
git add SKILL.md references/agent-usage.md README.md agents/openai.yaml tests/test_cli_smoke.py
git commit -m "docs: publish complete Phase 1 workflow"
```

---

## Final Review Gate

- [ ] Compare every section of
  `docs/superpowers/specs/2026-07-20-phase-1-real-world-repair-design.md` to the
  implementation and tests.
- [ ] Confirm `git status --short` contains no generated `.architecture-graph/`,
  `.codebase-graph/`, `dist/`, or virtual-environment files.
- [ ] Run the full validation command block from Task 7 on a clean checkout.
- [ ] Use `$requesting-code-review` before merging or releasing.
- [ ] After review approval, use `$finishing-a-development-branch` to choose
  merge, PR, or cleanup.
