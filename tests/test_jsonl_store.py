from pathlib import Path

import pytest

from architecture_graph.jsonl_store import (
    AtomicJsonlLedger,
    get_record,
    iter_records,
    select_records,
    write_records,
)
from architecture_graph.records import finalize_record


def record(record_id: str, path: str) -> dict[str, object]:
    return finalize_record({"id": record_id, "kind": "source", "path": path})


def observation_record(record_id: str) -> dict[str, object]:
    digest = "sha256:" + ("a" * 64)
    return finalize_record(
        {
            "id": record_id,
            "kind": "observation",
            "snapshot_id": "deterministic:" + ("b" * 64),
            "previous_current_snapshot_id": None,
            "base_deterministic_snapshot_id": "deterministic:" + ("b" * 64),
            "material_input_digest": digest,
            "source_revision_digest": digest,
            "branch": "main",
            "commit": "abc123",
            "dirty_fingerprint": digest,
            "observed_at": "2026-07-19T10:00:00Z",
        }
    )


def warning_record(record_id: str) -> dict[str, object]:
    return finalize_record(
        {
            "id": record_id,
            "kind": "warning",
            "code": "fixture",
            "message": "fixture warning",
            "source_version_id": None,
            "span": None,
            "possible_role": None,
            "derivation_ids": ["derivation:fixture"],
        }
    )


def test_snapshot_records_are_sorted_and_lf_terminated(tmp_path: Path) -> None:
    path = tmp_path / "sources.jsonl"
    write_records(path, [record("source:b", "b.md"), record("source:a", "a.md")])
    assert [item["id"] for item in iter_records(path, "source")] == [
        "source:a",
        "source:b",
    ]
    assert path.read_bytes().endswith(b"\n")


def test_get_and_select_do_not_create_missing_paths(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "sources.jsonl"
    assert get_record(path, "source:a") is None
    assert select_records(path, {}, None, 20) == []
    assert not path.parent.exists()


def test_select_applies_filters_fields_and_limit(tmp_path: Path) -> None:
    path = tmp_path / "sources.jsonl"
    write_records(path, [record("source:a", "a.md"), record("source:b", "b.md")])
    assert select_records(path, {"path": "b.md"}, ["id", "path"], 1) == [
        {"id": "source:b", "path": "b.md"}
    ]


def test_atomic_ledger_keeps_old_file_when_replace_fails(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "observations.jsonl"
    ledger = AtomicJsonlLedger(path)
    ledger.append(observation_record("observation:1"))
    before = path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("architecture_graph.jsonl_store.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        ledger.append(observation_record("observation:2"))
    assert path.read_bytes() == before


def test_malformed_or_duplicate_ledger_append_preserves_original_bytes(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_bytes(b'{"broken":\n')
    before = malformed.read_bytes()
    with pytest.raises(Exception):
        AtomicJsonlLedger(malformed).append(observation_record("observation:1"))
    assert malformed.read_bytes() == before

    valid = tmp_path / "valid.jsonl"
    item = observation_record("observation:1")
    AtomicJsonlLedger(valid).append(item)
    before = valid.read_bytes()
    with pytest.raises(ValueError, match="duplicate"):
        AtomicJsonlLedger(valid).append(item)
    assert valid.read_bytes() == before


def test_ledger_validates_new_and_existing_shapes_and_one_kind(
    tmp_path: Path,
) -> None:
    path = tmp_path / "observations.jsonl"
    ledger = AtomicJsonlLedger(path)
    ledger.append(observation_record("observation:1"))
    before = path.read_bytes()

    with pytest.raises(ValueError, match="ledger record kind"):
        ledger.append(warning_record("warning:1"))
    assert path.read_bytes() == before

    invalid_new = finalize_record({"id": "observation:2", "kind": "observation"})
    with pytest.raises(ValueError, match="missing fields"):
        ledger.append(invalid_new)
    assert path.read_bytes() == before

    invalid_existing = tmp_path / "invalid-existing.jsonl"
    write_records(
        invalid_existing,
        [finalize_record({"id": "observation:old", "kind": "observation"})],
    )
    invalid_before = invalid_existing.read_bytes()
    with pytest.raises(ValueError, match="missing fields"):
        AtomicJsonlLedger(invalid_existing).append(
            observation_record("observation:new")
        )
    assert invalid_existing.read_bytes() == invalid_before
