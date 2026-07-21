from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
from pathlib import Path
from collections.abc import Mapping, Sequence

import jmespath
from jmespath.exceptions import JMESPathError

from architecture_graph.canonical import canonical_bytes, canonical_dumps, sha256_digest
from architecture_graph.config import configuration_identity
from architecture_graph.corpus import resolve_corpus
from architecture_graph.fingerprint import pipeline_fingerprint
from architecture_graph.indexer import _stable_repository_capture
from architecture_graph.project import ProjectPaths
from architecture_graph.records import JSONValue, Record
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.sources import material_input_digest


@dataclass(frozen=True)
class QueryEnvelope:
    items: tuple[Record, ...]
    truncated: bool = False
    omitted_count: int = 0
    cursor: str | None = None
    max_chars: int = 12_000

    def as_json(self) -> dict[str, object]:
        return {
            "items": list(self.items),
            "truncated": self.truncated,
            "omitted_count": self.omitted_count,
            "cursor": self.cursor,
        }


def _project(record: Mapping[str, JSONValue], fields: Sequence[str] | None) -> Record:
    if fields is None:
        return dict(record)
    return {field: record[field] for field in fields if field in record}


def _cursor(binding: Mapping[str, object], offset: int) -> str:
    payload = {"binding": binding, "offset": offset}
    wrapped = {
        "payload": payload,
        "digest": sha256_digest(canonical_bytes(payload)),
    }
    return base64.urlsafe_b64encode(canonical_bytes(wrapped)).decode("ascii")


def _read_cursor(raw: str, binding: Mapping[str, object]) -> int:
    try:
        wrapped = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
        payload = wrapped["payload"]
        valid = wrapped["digest"] == sha256_digest(canonical_bytes(payload))
        if not valid or payload["binding"] != binding:
            raise ValueError
        offset = payload["offset"]
        if type(offset) is not int or offset < 0:
            raise ValueError
        return offset
    except (
        ValueError,
        KeyError,
        TypeError,
        UnicodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise ValueError("cursor does not match this query") from error


def render_query_envelope(envelope: QueryEnvelope, output_format: str) -> str:
    if output_format == "json":
        rendered = canonical_dumps(envelope.as_json()) + "\n"
    elif output_format == "markdown":
        lines = ["# Architecture Graph Query", ""]
        lines.extend(f"- `{canonical_dumps(item)}`" for item in envelope.items)
        lines.extend(
            [
                "",
                f"Truncated: {str(envelope.truncated).lower()}",
                f"Omitted: {envelope.omitted_count}",
                f"Cursor: {envelope.cursor or ''}",
            ]
        )
        rendered = "\n".join(lines) + "\n"
    else:
        raise ValueError(f"unknown output format: {output_format}")
    if len(rendered) > envelope.max_chars:
        raise ValueError("query envelope exceeds max_chars")
    return rendered


def _fit(envelope: QueryEnvelope) -> QueryEnvelope:
    items = list(envelope.items)
    omitted = envelope.omitted_count
    while True:
        candidate = QueryEnvelope(
            tuple(items),
            envelope.truncated or omitted > envelope.omitted_count,
            omitted,
            envelope.cursor,
            envelope.max_chars,
        )
        try:
            render_query_envelope(candidate, "json")
            return candidate
        except ValueError:
            if not items:
                raise
            items.pop()
            omitted += 1


def get_snapshot_record(
    reader: SnapshotReader,
    record_type: str,
    record_id: str,
    fields: Sequence[str] | None = None,
    max_chars: int = 12_000,
) -> QueryEnvelope:
    record = reader.get(record_type, record_id)
    if record is None:
        raise KeyError(f"record not found: {record_id}")
    return _fit(QueryEnvelope((_project(record, fields),), max_chars=max_chars))


def find_snapshot_records(
    reader: SnapshotReader,
    record_type: str,
    filters: Mapping[str, JSONValue] | None = None,
    contains: str | None = None,
    fields: Sequence[str] | None = None,
    limit: int = 20,
    max_chars: int = 12_000,
    cursor: str | None = None,
    expression: str | None = None,
) -> QueryEnvelope:
    if limit < 1:
        raise ValueError("limit must be positive")
    selected_filters = dict(filters or {})
    binding = {
        "snapshot_id": reader.snapshot_id,
        "record_type": record_type,
        "filters": selected_filters,
        "contains": contains,
        "fields": list(fields) if fields is not None else None,
        "limit": limit,
        "expression": expression,
    }
    offset = 0 if cursor is None else _read_cursor(cursor, binding)
    matches: list[Record] = []
    for record in reader.iter(record_type):
        if any(record.get(key) != value for key, value in selected_filters.items()):
            continue
        if contains is not None and contains.casefold() not in canonical_dumps(record).casefold():
            continue
        matches.append(dict(record))
    candidates = matches[offset : offset + limit]
    retained: list[tuple[int, Record]] = []
    try:
        for position, record in enumerate(candidates):
            if expression is None or bool(jmespath.search(expression, record)):
                retained.append((position, _project(record, fields)))
    except JMESPathError as error:
        raise ValueError(f"invalid JMESPath expression: {error}") from error
    while True:
        if retained:
            next_offset = offset + retained[-1][0] + 1
        else:
            next_offset = offset + len(candidates)
        omitted = max(0, len(matches) - next_offset)
        next_cursor = _cursor(binding, next_offset) if omitted else None
        envelope = QueryEnvelope(
            tuple(item for _, item in retained),
            truncated=omitted > 0 or len(retained) < len(candidates),
            omitted_count=omitted + (len(candidates) - len(retained)),
            cursor=next_cursor,
            max_chars=max_chars,
        )
        try:
            render_query_envelope(envelope, "json")
            return envelope
        except ValueError:
            if not retained:
                raise
            retained.pop()


def memory_status(
    paths: Sequence[Path],
    *,
    memory_root: Path | None = None,
    config_path: Path | None = None,
    fields: Sequence[str] | None = None,
    max_chars: int = 12_000,
) -> QueryEnvelope:
    if not paths:
        raise ValueError("at least one corpus input is required")
    from architecture_graph.corpus import find_git_worktree

    repository = find_git_worktree(paths[0])
    selection = resolve_corpus(paths, configuration_identity(repository, config_path))
    project = ProjectPaths.for_corpus(selection, memory_root)
    if memory_root is not None and selection.inputs == (".",):
        legacy = ProjectPaths.resolve(repository, memory_root)
        if legacy.current_path.is_file():
            project = legacy
    required_ignore = None
    if memory_root is None:
        import os
        import subprocess

        if not os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT"):
            ignored = subprocess.run(
                ["git", "-C", str(repository), "check-ignore", "-q", ".architecture-graph/"],
                check=False,
            ).returncode == 0
            if not ignored:
                required_ignore = ".architecture-graph/"
    if not project.current_path.is_file():
        item: Record = {
            "state": "missing",
            "fresh": False,
            "corpus_id": selection.corpus_id,
            "required_ignore": required_ignore,
            "writable": required_ignore is None,
        }
        if fields is not None and "state" not in fields:
            fields = ("state", *fields)
        return _fit(QueryEnvelope((_project(item, fields),), max_chars=max_chars))
    reader = SnapshotReader.open(project)
    capture = _stable_repository_capture(
        repository, config_path, None, selection.inputs
    )
    digest = material_input_digest(
        capture.inputs, capture.config, pipeline_fingerprint().digest
    )
    fresh = reader.manifest.get("material_input_digest") == digest
    item = {
        "state": "fresh" if fresh else "stale",
        "fresh": fresh,
        "corpus_id": selection.corpus_id,
        "snapshot_id": reader.snapshot_id,
        "snapshot_kind": reader.manifest.get("snapshot_kind"),
        "required_ignore": required_ignore,
        "writable": required_ignore is None,
    }
    if fields is not None and "state" not in fields:
        fields = ("state", *fields)
    return _fit(QueryEnvelope((_project(item, fields),), max_chars=max_chars))
