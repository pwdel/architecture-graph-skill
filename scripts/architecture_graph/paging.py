from __future__ import annotations

from collections.abc import Mapping, Sequence

from architecture_graph.query import QueryEnvelope, _cursor, _project, _read_cursor, render_query_envelope
from architecture_graph.records import JSONValue, Record
from architecture_graph.errors import RecordTooLargeError


def page_records(records: Sequence[Record], *, binding: Mapping[str, object], fields: Sequence[str] | None, limit: int, max_chars: int, cursor: str | None = None) -> QueryEnvelope:
    if limit < 1: raise ValueError("limit must be positive")
    offset = 0 if cursor is None else _read_cursor(cursor, binding)
    selected = [_project(record, fields) for record in records[offset:offset + limit]]
    while True:
        next_offset = offset + len(selected)
        omitted = max(0, len(records) - next_offset)
        envelope = QueryEnvelope(tuple(selected), truncated=bool(omitted), omitted_count=omitted, cursor=_cursor(binding, next_offset) if omitted else None, max_chars=max_chars)
        try:
            render_query_envelope(envelope, "json")
            return envelope
        except ValueError:
            if not selected:
                raise
            if len(selected) == 1:
                record_id = str(selected[0].get("id", "unknown"))
                probe = QueryEnvelope(tuple(selected), truncated=bool(len(records) - offset - 1), omitted_count=max(0, len(records) - offset - 1), cursor=None, max_chars=10**9)
                minimum_chars = len(render_query_envelope(probe, "json"))
                raise RecordTooLargeError(record_id, max_chars, minimum_chars)
            selected.pop()
