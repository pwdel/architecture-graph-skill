import json
from pathlib import Path

import pytest
from architecture_graph.errors import RecordTooLargeError
from architecture_graph.paging import page_records

from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.query import (
    find_snapshot_records,
    get_snapshot_record,
    memory_status,
    render_query_envelope,
)
from architecture_graph.snapshot import SnapshotReader


def _design_repo(architecture_repo: Path) -> tuple[Path, object]:
    from conftest import git, ignore_architecture_graph

    plan = architecture_repo / "lib" / "design" / "design-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        json.dumps(
            {
                "title": "Plan",
                "decision_log": [
                    {"status": "accepted", "decision": "backend owns truth"},
                    {"status": "proposed", "decision": "add test tooling"},
                ],
            }
        )
    )
    git(architecture_repo, "add", "lib/design/design-plan.json")
    git(architecture_repo, "commit", "-m", "add design plan")
    ignore_architecture_graph(architecture_repo)
    result = index_corpus((plan,))
    return plan, result


def test_status_is_read_only_and_tracks_freshness(architecture_repo: Path) -> None:
    plan = architecture_repo / "docs" / "adr" / "ADR-001.md"
    missing = memory_status((plan,))
    assert missing.items[0]["state"] == "missing"
    assert not (architecture_repo / ".architecture-graph").exists()
    from conftest import ignore_architecture_graph

    ignore_architecture_graph(architecture_repo)
    index_corpus((plan,))
    assert memory_status((plan,)).items[0]["state"] == "fresh"
    plan.write_text(plan.read_text() + "\nChanged.\n")
    assert memory_status((plan,)).items[0]["state"] == "stale"


def test_get_and_find_are_bounded_and_cursor_stable(architecture_repo: Path) -> None:
    _, result = _design_repo(architecture_repo)
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    source = next(reader.iter("sources"))
    exact = get_snapshot_record(
        reader, "sources", source["id"], fields=("id", "path")
    )
    assert exact.items == ({"id": source["id"], "path": source["path"]},)
    first = find_snapshot_records(
        reader, "segments", fields=("id", "text"), limit=1
    )
    assert len(first.items) == 1
    assert first.cursor is not None
    second = find_snapshot_records(
        reader,
        "segments",
        fields=("id", "text"),
        limit=1,
        cursor=first.cursor,
    )
    assert second.items != first.items
    with pytest.raises(ValueError, match="cursor"):
        find_snapshot_records(
            reader, "segments", contains="proposed", cursor=first.cursor
        )
    rendered = render_query_envelope(first, "json")
    assert rendered.endswith("\n")
    assert len(rendered) <= first.max_chars


def test_character_budget_cursor_does_not_skip_trimmed_items() -> None:
    class Reader:
        snapshot_id = "deterministic:" + ("a" * 64)

        def iter(self, record_type):
            return iter(
                [
                    {"id": f"segment:{index}", "text": str(index) * 120}
                    for index in range(3)
                ]
            )

    reader = Reader()
    first = find_snapshot_records(reader, "segments", limit=2, max_chars=700)
    assert len(first.items) == 1
    second = find_snapshot_records(
        reader, "segments", limit=2, max_chars=700, cursor=first.cursor
    )
    assert second.items[0]["id"] == "segment:1"


def test_malformed_cursor_and_jmespath_are_user_errors() -> None:
    class Reader:
        snapshot_id = "deterministic:" + ("b" * 64)

        def iter(self, record_type):
            return iter([{"id": "segment:1", "text": "accepted"}])

    with pytest.raises(ValueError, match="cursor"):
        find_snapshot_records(Reader(), "segments", cursor="not-base64")
    with pytest.raises(ValueError, match="JMESPath"):
        find_snapshot_records(Reader(), "segments", expression="[")


def test_oversized_first_record_is_an_explicit_error() -> None:
    with pytest.raises(RecordTooLargeError) as raised:
        page_records(
            [{"id": "term:oversized", "text": "x" * 5_000}],
            binding={"command": "terms"}, fields=None, limit=1, max_chars=100,
        )
    assert raised.value.record_id == "term:oversized"
    assert raised.value.minimum_chars > 100
