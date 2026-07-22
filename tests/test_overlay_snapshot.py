from pathlib import Path

import json
import pytest

from architecture_graph.overlay_snapshot import (
    RationaleOverlayPaths,
    RationaleOverlayReader,
    build_overlay_manifest,
    publish_rationale_overlay,
)
from architecture_graph.rationale_resolver import resolve_rationales
from test_phase2_golden import _index


def test_overlay_paths_are_separate_from_base_snapshots(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    paths = RationaleOverlayPaths.for_base(reader.project, reader.snapshot_id)
    assert reader.project.snapshots_dir not in paths.root.parents
    assert paths.root == reader.project.project_dir / "overlays" / "rationale" / reader.snapshot_id.replace(":", "-")


def test_reader_rejects_overlay_with_wrong_base_ranking_digest(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    paths = RationaleOverlayPaths.for_base(reader.project, reader.snapshot_id)
    result = resolve_rationales(reader)
    manifest = build_overlay_manifest(reader, result)
    publish_rationale_overlay(paths, manifest, result, reader)
    manifest_path = paths.snapshots / manifest.overlay_id.replace(":", "-") / "MANIFEST.json"
    raw = json.loads(manifest_path.read_text())
    raw["base_ranking_digest"] = "sha256:" + "0" * 64
    manifest_path.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="overlay incompatible"):
        RationaleOverlayReader.open(paths, base=reader)


def test_publication_rejects_stale_base_before_advancing_current(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    paths = RationaleOverlayPaths.for_base(reader.project, reader.snapshot_id)
    result = resolve_rationales(reader)
    manifest = build_overlay_manifest(reader, result)
    rankings = reader.snapshot_dir / "rankings.jsonl"
    rankings.write_bytes(rankings.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="base snapshot changed"):
        publish_rationale_overlay(paths, manifest, result, reader)
    assert not paths.current.exists()
