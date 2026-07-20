import math

import pytest

from architecture_graph.canonical import canonical_dumps, stable_id
from architecture_graph.records import (
    SourceSpan,
    finalize_record,
    validate_record,
    validate_record_shape,
)


VALID_DIGEST = "sha256:" + "a" * 64


def test_canonical_json_normalizes_unicode_keys_and_floats() -> None:
    left = {"z": -0.0, "name": "Cafe\u0301", "score": 0.1234567891}
    right = {"score": 0.12345679, "name": "Café", "z": 0.0}
    assert canonical_dumps(left) == canonical_dumps(right)
    assert canonical_dumps(left) == '{"name":"Café","score":0.12345679,"z":0.0}'


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="finite"):
        canonical_dumps({"score": math.nan})


def test_canonical_json_rejects_non_string_and_colliding_normalized_keys() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        canonical_dumps({1: "value"})
    with pytest.raises(ValueError, match="duplicate normalized key"):
        canonical_dumps({"Cafe\u0301": 1, "Café": 2})


def test_source_span_requires_positive_ordered_coordinates() -> None:
    with pytest.raises(ValueError, match="positive"):
        SourceSpan(0, 1)
    with pytest.raises(ValueError, match="before start"):
        SourceSpan(3, 2)
    with pytest.raises(ValueError, match="exclusive"):
        SourceSpan(3, 3, 5, 5)


def test_stable_id_is_repeatable_and_kind_scoped() -> None:
    assert stable_id("source", "docs/adr/1.md", "abc") == stable_id(
        "source", "docs/adr/1.md", "abc"
    )
    assert stable_id("source", "docs/adr/1.md", "abc") != stable_id(
        "segment", "docs/adr/1.md", "abc"
    )


def test_finalized_record_validates_content_digest() -> None:
    record = finalize_record(
        {"id": "source:abc", "kind": "source", "path": "docs/adr/1.md"}
    )
    validate_record(record, "source")
    record["path"] = "docs/adr/2.md"
    with pytest.raises(ValueError, match="content digest"):
        validate_record(record, "source")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id": "claim:wrong-kind"}, "evidence ID"),
        ({"source_version_id": "claim:wrong-kind"}, "source_version_id"),
        ({"source_content_hash": "sha256:short"}, "source_content_hash"),
        ({"span": {"start_line": 0, "end_line": 1, "start_column": 1, "end_column": None}}, "span"),
        ({"text": 7}, "text"),
        ({"derivation_ids": []}, "derivation_ids"),
    ],
)
def test_phase1_shapes_fail_closed(changes: dict[str, object], message: str) -> None:
    record = finalize_record(
        {
            "id": "evidence:" + "b" * 64,
            "kind": "evidence",
            "source_version_id": "source:" + "c" * 64,
            "segment_id": "segment:" + "d" * 64,
            "path": "docs/adr/1.md",
            "source_content_hash": VALID_DIGEST,
            "span": {"start_line": 1, "end_line": 1, "start_column": 1, "end_column": 2},
            "text": "A",
            "derivation_ids": ["derivation:" + "e" * 64],
        }
    )
    with pytest.raises(ValueError, match=message):
        validate_record_shape({**record, **changes})


def test_derivation_producer_enum_is_closed() -> None:
    record = finalize_record(
        {
            "id": "derivation:" + "b" * 64,
            "kind": "derivation",
            "producer_kind": "robot",
            "method": "rule",
            "tool": "architecture-graph",
            "tool_version": "0.1.0",
            "model": None,
            "model_version": None,
            "model_artifact_digest": None,
            "configuration_digest": VALID_DIGEST,
            "pipeline_digest": VALID_DIGEST,
            "input_ids": ["source:" + "c" * 64],
            "output_kind": "segment_set",
            "output_identity_key": "source:" + "c" * 64,
            "created_at": None,
        }
    )
    with pytest.raises(ValueError, match="producer_kind"):
        validate_record_shape(record)
