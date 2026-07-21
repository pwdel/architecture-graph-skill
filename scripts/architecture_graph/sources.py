from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess
from collections.abc import Sequence

from architecture_graph.canonical import canonical_bytes, sha256_digest, stable_id
from architecture_graph.config import (
    ProjectConfig,
    path_matches,
    source_authority,
    source_role,
)


@dataclass(frozen=True)
class SourceInput:
    relative_path: str
    absolute_path: Path
    source_kind: str
    document_role: str
    authority_class: str
    authority_basis: str
    tracked: bool
    git_blob: str | None
    content_hash: str
    text: str
    decode_error: str | None


def _git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    ).stdout


def _kind(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    return {
        ".md": "markdown",
        ".markdown": "markdown",
        ".mmd": "mermaid",
        ".mermaid": "mermaid",
        ".puml": "plantuml",
        ".plantuml": "plantuml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".txt": "text",
    }.get(suffix, "unsupported")


def _read_source(root: Path, relative_path: str, tracked: bool) -> SourceInput:
    absolute = (root / relative_path).resolve()
    if not absolute.is_relative_to(root.resolve()):
        raise ValueError(f"source escapes repository root: {relative_path}")
    raw = absolute.read_bytes()
    try:
        text = raw.decode("utf-8")
        decode_error = None
    except UnicodeDecodeError as error:
        text = ""
        decode_error = str(error)
    git_blob = None
    if tracked:
        result = subprocess.run(
            ["git", "-C", str(root), "hash-object", "--stdin"],
            check=True,
            input=raw,
            capture_output=True,
        )
        git_blob = result.stdout.decode("ascii").strip() or None
    return SourceInput(
        relative_path=relative_path,
        absolute_path=absolute,
        source_kind=_kind(relative_path),
        document_role="architecture",
        authority_class="maintained_architecture",
        authority_basis="default",
        tracked=tracked,
        git_blob=git_blob,
        content_hash=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        text=text,
        decode_error=decode_error,
    )


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
        value
        for value in selected_paths
        if value != "." and (root / value).is_file()
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
    for path in config.untracked:
        normalized = Path(path).as_posix()
        if not any(_inside_selection(normalized, value) for value in selected_paths):
            continue
        if normalized in selected:
            continue
        if normalized in tracked_set:
            raise ValueError(
                "configured untracked source is tracked but excluded by include/exclude: "
                f"{normalized}"
            )
        if not (root / normalized).is_file():
            raise ValueError(f"configured untracked source does not exist: {normalized}")
        if _kind(normalized) == "unsupported":
            raise ValueError(f"unsupported configured source: {normalized}")
        if _kind(normalized) == "text" and not path_matches(
            normalized, config.plaintext
        ):
            raise ValueError(
                f"configured untracked plaintext requires plaintext selection: {normalized}"
            )
        selected[normalized] = False
    for normalized in explicit_files:
        if normalized not in selected:
            selected[normalized] = normalized in tracked_set
    inputs = [_read_source(root, path, tracked) for path, tracked in sorted(selected.items())]
    resolved: list[SourceInput] = []
    for item in inputs:
        authority_class, authority_basis = source_authority(item.relative_path, config)
        resolved.append(SourceInput(
            relative_path=item.relative_path,
            absolute_path=item.absolute_path,
            source_kind=item.source_kind,
            document_role=source_role(item.relative_path, config),
            authority_class=authority_class,
            authority_basis=authority_basis,
            tracked=item.tracked,
            git_blob=item.git_blob,
            content_hash=item.content_hash,
            text=item.text,
            decode_error=item.decode_error,
        ))
    return resolved


def source_record_base(
    item: SourceInput, logical_source_id: str
) -> dict[str, object]:
    if not logical_source_id.startswith("logical-source:"):
        raise ValueError("logical source ID must start with logical-source:")
    return {
        "id": source_record_id(item),
        "kind": "source",
        "logical_source_id": logical_source_id,
        "path": item.relative_path,
        "source_kind": item.source_kind,
        "document_role": item.document_role,
        "authority_class": item.authority_class,
        "authority_basis": item.authority_basis,
        "tracked": item.tracked,
        "git_blob": item.git_blob,
        "content_hash": item.content_hash,
        "decodable": item.decode_error is None,
    }


def source_record_id(item: SourceInput) -> str:
    return stable_id("source", item.relative_path, item.content_hash)


def material_input_digest(
    inputs: Sequence[SourceInput], config: ProjectConfig, pipeline_digest: str
) -> str:
    ordered_inputs = sorted(inputs, key=lambda item: item.relative_path)
    for previous, current in zip(ordered_inputs, ordered_inputs[1:]):
        if previous.relative_path == current.relative_path:
            raise ValueError(f"duplicate source path: {current.relative_path}")
    payload = {
        "sources": [
            {
                "path": item.relative_path,
                "content_hash": item.content_hash,
                "source_kind": item.source_kind,
                "document_role": item.document_role,
                "authority_class": item.authority_class,
                "authority_basis": item.authority_basis,
                "tracked": item.tracked,
            }
            for item in ordered_inputs
        ],
        "config": config.as_digest_input(),
        "pipeline_digest": pipeline_digest,
    }
    return sha256_digest(canonical_bytes(payload))
