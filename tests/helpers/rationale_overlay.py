from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from architecture_graph.canonical import sha256_digest
from architecture_graph.snapshot import SnapshotReader


@dataclass(frozen=True)
class BaseArtifactCapture:
    snapshot_id: str
    ranking_digest: str
    semantic_schema: int
    scoring_rule_version: str
    files: tuple[tuple[str, bytes], ...]


def capture_frozen_base(reader: SnapshotReader) -> BaseArtifactCapture:
    names = ("decisions.jsonl", "edges.jsonl", "rankings.jsonl")
    files = tuple((name, (reader.snapshot_dir / name).read_bytes()) for name in names)
    rankings = dict(files)["rankings.jsonl"]
    return BaseArtifactCapture(
        reader.snapshot_id,
        sha256_digest(rankings),
        int(reader.manifest["schema_versions"]["semantic"]),
        "scoring-v1",
        files,
    )
