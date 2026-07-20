from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
import os
from pathlib import Path
import tempfile

import jsonlines

from architecture_graph.canonical import canonical_dumps
from architecture_graph.records import (
    JSONValue,
    Record,
    validate_record,
    validate_record_shape,
)


def _write(path: Path, records: Iterable[Record], *, sort_ids: bool) -> None:
    materialized = list(records)
    if sort_ids:
        materialized.sort(key=lambda item: str(item["id"]))
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = jsonlines.Writer(handle, dumps=canonical_dumps, flush=True)
        try:
            writer.write_all(materialized)
        finally:
            writer.close()


def write_records(path: Path, records: Iterable[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, records, sort_ids=True)


def iter_records(
    path: Path, expected_kind: str | None = None
) -> Iterator[Record]:
    if not path.is_file():
        return
    with jsonlines.open(path, mode="r") as reader:
        for raw in reader:
            if not isinstance(raw, dict):
                raise ValueError(f"JSONL record is not an object: {path}")
            validate_record(raw, expected_kind)
            yield raw


def get_record(path: Path, record_id: str) -> Record | None:
    for record in iter_records(path):
        if record["id"] == record_id:
            return record
    return None


def select_records(
    path: Path,
    filters: Mapping[str, JSONValue],
    fields: Sequence[str] | None,
    limit: int,
) -> list[Record]:
    if limit < 1:
        raise ValueError("limit must be positive")
    selected: list[Record] = []
    for record in iter_records(path):
        if any(record.get(key) != value for key, value in filters.items()):
            continue
        if fields is None:
            projected = dict(record)
        else:
            projected = {field: record[field] for field in fields if field in record}
        selected.append(projected)
        if len(selected) == limit:
            break
    return selected


class AtomicJsonlLedger:
    """Crash-safe record append; callers must hold the project publication lock."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: Record) -> None:
        validate_record(record)
        validate_record_shape(record)
        existing = list(iter_records(self.path))
        for item in existing:
            validate_record_shape(item)
            if item["kind"] != record["kind"]:
                raise ValueError(
                    f"ledger record kind mismatch: {item['kind']} != {record['kind']}"
                )
        if any(item["id"] == record["id"] for item in existing):
            raise ValueError(f"duplicate ledger record id: {record['id']}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        temporary = Path(raw_path)
        os.close(descriptor)
        try:
            _write(temporary, [*existing, record], sort_ids=False)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)
