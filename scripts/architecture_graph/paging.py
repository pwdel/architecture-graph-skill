from __future__ import annotations

from collections.abc import Mapping, Sequence

from architecture_graph.query import QueryEnvelope, _cursor, _fit, _project, _read_cursor
from architecture_graph.records import JSONValue, Record


def page_records(records: Sequence[Record], *, binding: Mapping[str, object], fields: Sequence[str] | None, limit: int, max_chars: int, cursor: str | None = None) -> QueryEnvelope:
    if limit < 1: raise ValueError("limit must be positive")
    offset = 0 if cursor is None else _read_cursor(cursor, binding)
    selected = [_project(record, fields) for record in records[offset:offset + limit]]
    next_offset = offset + len(selected)
    omitted = max(0, len(records) - next_offset)
    return _fit(QueryEnvelope(tuple(selected), truncated=bool(omitted), omitted_count=omitted, cursor=_cursor(binding, next_offset) if omitted else None, max_chars=max_chars))
