from __future__ import annotations

from contextlib import AbstractContextManager
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from urllib.parse import urlsplit, urlunsplit

from architecture_graph.canonical import canonical_bytes, sha256_digest
from architecture_graph.records import JSONValue


class RepositoryStateError(RuntimeError):
    pass


def _git_bytes_checked(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        ).stdout
    except OSError as error:
        raise RepositoryStateError("Git executable could not run") from error
    except subprocess.CalledProcessError as error:
        operation = args[0] if args else "command"
        raise RepositoryStateError(f"Git {operation} failed for repository") from error


def _git_optional(
    root: Path,
    *args: str,
    absent_returncodes: tuple[int, ...] = (1,),
) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise RepositoryStateError("Git executable could not run") from error
    if result.returncode != 0:
        if result.returncode in absent_returncodes:
            return None
        operation = args[0] if args else "command"
        raise RepositoryStateError(f"Git {operation} failed for repository")
    try:
        value = result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise RepositoryStateError("Git returned non-UTF-8 identity output") from error
    return value or None


def _decode_git_path(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RepositoryStateError("Git returned a non-UTF-8 path") from error


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
    remote = _git_optional(
        resolved,
        "config",
        "--get",
        "remote.origin.url",
        absent_returncodes=(1,),
    )
    identity = f"{normalize_remote(remote or '')}\n{resolved.as_posix()}".encode(
        "utf-8"
    )
    return hashlib.sha256(identity).hexdigest()


def _path_digest(path: Path) -> str | None:
    try:
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            raw = path.read_bytes()
        elif stat.S_ISLNK(mode):
            raw = os.fsencode(os.readlink(path))
        elif not path.exists():
            return None
        else:
            raise RepositoryStateError(
                f"unsupported dirty path type: {path.as_posix()}"
            )
        return sha256_digest(raw)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise RepositoryStateError(f"cannot read dirty path: {path.name}") from error


def _index_digest(root: Path, path: str, status: str) -> str | None:
    if status == "D":
        return None
    return sha256_digest(_git_bytes_checked(root, "show", f":{path}"))


def _dirty_preimage_once(root: Path) -> dict[str, JSONValue]:
    raw = _git_bytes_checked(
        root, "status", "--porcelain=v2", "-z", "--untracked-files=all"
    )
    fields = raw.split(b"\0")
    entries: list[dict[str, JSONValue]] = []
    cursor = 0
    while cursor < len(fields) and fields[cursor]:
        field = fields[cursor]
        cursor += 1
        tag = field[:1]
        original_path: str | None = None
        if tag == b"2":
            if cursor >= len(fields) or not fields[cursor]:
                raise RepositoryStateError("Git returned malformed rename status")
            original_path = _decode_git_path(fields[cursor])
            cursor += 1
        if tag == b"?":
            path = _decode_git_path(field[2:])
            absolute = root / path
            try:
                mode = format(absolute.lstat().st_mode, "06o")
            except OSError as error:
                raise RepositoryStateError(
                    f"cannot stat untracked path: {path}"
                ) from error
            entries.append(
                {
                    "status": "??",
                    "submodule": None,
                    "modes": [mode],
                    "path": path,
                    "original_path": None,
                    "rename_score": None,
                    "staged_content_digest": None,
                    "worktree_content_digest": _path_digest(absolute),
                }
            )
            continue
        limits = {b"1": 8, b"2": 9, b"u": 10}
        if tag not in limits:
            raise RepositoryStateError("Git returned unsupported status record")
        parts = _decode_git_path(field).split(" ", maxsplit=limits[tag])
        expected = limits[tag] + 1
        if len(parts) != expected:
            raise RepositoryStateError("Git returned malformed status record")
        xy = parts[1]
        modes = parts[3:6] if tag in {b"1", b"2"} else parts[3:7]
        path = parts[-1]
        entries.append(
            {
                "status": xy,
                "submodule": parts[2],
                "modes": modes,
                "path": path,
                "original_path": original_path,
                "rename_score": parts[-2] if tag == b"2" else None,
                "staged_content_digest": (
                    _index_digest(root, path, xy[0]) if xy[0] != "." else None
                ),
                "worktree_content_digest": (
                    _path_digest(root / path) if xy[1] != "." else None
                ),
            }
        )
    return {
        "schema_version": 1,
        "entries": sorted(
            entries,
            key=lambda item: (
                str(item["path"]),
                str(item["original_path"] or ""),
                str(item["status"]),
            ),
        ),
    }


def _stable_dirty_preimage(root: Path) -> Mapping[str, JSONValue]:
    first = _dirty_preimage_once(root)
    second = _dirty_preimage_once(root)
    if canonical_bytes(first) != canonical_bytes(second):
        raise RepositoryStateError("repository changed while Git state was captured")
    return second


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
    branch_before = _git_optional(root, "symbolic-ref", "--short", "-q", "HEAD")
    commit_before = _git_optional(
        root, "rev-parse", "HEAD", absent_returncodes=(128,)
    )
    dirty_preimage = _stable_dirty_preimage(root)
    branch = _git_optional(root, "symbolic-ref", "--short", "-q", "HEAD")
    commit = _git_optional(root, "rev-parse", "HEAD", absent_returncodes=(128,))
    if (branch, commit) != (branch_before, commit_before):
        raise RepositoryStateError(
            "repository HEAD changed while Git state was captured"
        )
    timestamp = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "branch": branch,
        "commit": commit,
        "dirty_fingerprint": sha256_digest(canonical_bytes(dirty_preimage)),
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
    corpus_file: Path
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
            corpus_file=project_dir / "CORPUS.json",
            lock_path=project_dir / ".publish.lock",
        )

    @classmethod
    def for_corpus(
        cls, selection, memory_root: Path | None = None
    ) -> "ProjectPaths":
        configured = os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT")
        base = (
            memory_root.resolve()
            if memory_root is not None
            else Path(configured).resolve()
            if configured
            else selection.repository / ".architecture-graph"
        )
        projects_root = base / "corpora"
        project_dir = projects_root / selection.corpus_id
        return cls(
            root=selection.repository,
            project_id=selection.corpus_id,
            projects_root=projects_root,
            project_dir=project_dir,
            snapshots_dir=project_dir / "snapshots",
            reviews_dir=project_dir / "reviews",
            cache_dir=project_dir / "cache",
            current_path=project_dir / "current.json",
            observations_path=project_dir / "observations.jsonl",
            project_file=project_dir / "PROJECT.json",
            corpus_file=project_dir / "CORPUS.json",
            lock_path=project_dir / ".publish.lock",
        )
