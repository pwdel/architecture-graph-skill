from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit, urlunsplit

from architecture_graph.canonical import sha256_digest
from architecture_graph.records import JSONValue


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def normalize_remote(remote: str) -> str:
    value = remote.strip().replace("\\", "/")
    if not value:
        return ""
    if value.startswith("git@") and ":" in value:
        host, path = value.split(":", 1)
        value = f"ssh://{host.casefold()}/{path}"
    parsed = urlsplit(value)
    if parsed.scheme:
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return urlunsplit(
            (parsed.scheme.casefold(), parsed.netloc.casefold(), path, "", "")
        )
    return value.removesuffix(".git").rstrip("/")


def project_id(root: Path) -> str:
    resolved = root.resolve()
    remote = _git(resolved, "config", "--get", "remote.origin.url", check=False)
    identity = f"{normalize_remote(remote)}\n{resolved.as_posix()}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


class ProjectLock(AbstractContextManager["ProjectLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None

    def __enter__(self) -> "ProjectLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+")
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


def capture_git_observation(
    root: Path, observed_at: str | None = None
) -> dict[str, JSONValue]:
    branch = _git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False) or None
    commit = _git(root, "rev-parse", "HEAD", check=False) or None
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v2", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    timestamp = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "branch": branch,
        "commit": commit,
        "dirty_fingerprint": sha256_digest(dirty),
        "observed_at": timestamp,
    }


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    project_id: str
    projects_root: Path
    project_dir: Path
    snapshots_dir: Path
    reviews_dir: Path
    cache_dir: Path
    current_path: Path
    observations_path: Path
    project_file: Path
    lock_path: Path

    @classmethod
    def resolve(cls, root: Path, memory_root: Path | None = None) -> "ProjectPaths":
        resolved = root.resolve()
        if memory_root is not None:
            projects_root = memory_root.resolve()
        elif os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT"):
            projects_root = Path(os.environ["ARCHITECTURE_GRAPH_MEMORY_ROOT"]).resolve()
        else:
            codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
            projects_root = codex_home / "memories" / "architecture-graph" / "projects"
        identity = project_id(resolved)
        project_dir = projects_root / identity
        return cls(
            root=resolved,
            project_id=identity,
            projects_root=projects_root,
            project_dir=project_dir,
            snapshots_dir=project_dir / "snapshots",
            reviews_dir=project_dir / "reviews",
            cache_dir=project_dir / "cache",
            current_path=project_dir / "current.json",
            observations_path=project_dir / "observations.jsonl",
            project_file=project_dir / "PROJECT.json",
            lock_path=project_dir / ".publish.lock",
        )
