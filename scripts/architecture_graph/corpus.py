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
    relative: list[str] = []
    for raw in paths:
        selected = raw.resolve()
        if not selected.exists():
            raise ValueError(f"corpus input does not exist: {raw}")
        if not selected.is_file() and not selected.is_dir():
            raise ValueError(f"corpus input is not a file or directory: {raw}")
        if find_git_worktree(selected) != repository:
            raise ValueError("all corpus inputs must belong to the same Git worktree")
        value = selected.relative_to(repository).as_posix()
        relative.append(value or ".")
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
    for path in paths:
        if not path.resolve().exists():
            raise ValueError(f"corpus input does not exist: {path}")
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
