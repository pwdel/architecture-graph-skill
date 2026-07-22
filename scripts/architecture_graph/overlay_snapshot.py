from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

from architecture_graph.canonical import atomic_write_json, canonical_bytes, sha256_digest
from architecture_graph.jsonl_store import iter_records, write_records
from architecture_graph.overlay_contract import validate_rationale_overlay
from architecture_graph.overlay_types import RationaleOverlayManifest, RationaleOverlayResult
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader


@dataclass(frozen=True)
class RationaleOverlayPaths:
    root: Path
    snapshots: Path
    current: Path

    @classmethod
    def for_base(cls, project: ProjectPaths, base_snapshot_id: str) -> "RationaleOverlayPaths":
        root = project.project_dir / "overlays" / "rationale" / base_snapshot_id.replace(":", "-")
        return cls(root, root / "snapshots", root / "CURRENT.json")


@dataclass(frozen=True)
class RationaleOverlayReader:
    overlay_id: str
    directory: Path
    manifest: dict[str, object]

    @classmethod
    def open(cls, paths: RationaleOverlayPaths, overlay_id: str | None = None) -> "RationaleOverlayReader":
        if overlay_id is None:
            overlay_id = json.loads(paths.current.read_text())["overlay_id"]
        directory = paths.snapshots / overlay_id.replace(":", "-")
        return cls(overlay_id, directory, json.loads((directory / "MANIFEST.json").read_text()))

    def iter_resolutions(self):
        return iter_records(self.directory / "rationale-resolutions.jsonl")


def publish_rationale_overlay(paths: RationaleOverlayPaths, manifest: RationaleOverlayManifest, result: RationaleOverlayResult, base: SnapshotReader) -> str:
    issues = validate_rationale_overlay(result.resolutions, base)
    if issues:
        raise ValueError(f"rationale overlay validation failed: {issues[0].field}: {issues[0].message}")
    if manifest.base_snapshot_id != base.snapshot_id:
        raise ValueError("base snapshot changed")
    paths.snapshots.mkdir(parents=True, exist_ok=True)
    target = paths.snapshots / manifest.overlay_id.replace(":", "-")
    if not target.exists():
        stage = Path(tempfile.mkdtemp(prefix=".rationale-", dir=paths.snapshots))
        write_records(stage / "rationale-resolutions.jsonl", result.resolutions)
        write_records(stage / "derivations.jsonl", result.derivations)
        write_records(stage / "warnings.jsonl", result.warnings)
        atomic_write_json(stage / "MANIFEST.json", manifest.as_record())
        if manifest.base_snapshot_id != base.snapshot_id:
            raise ValueError("base snapshot changed")
        os.replace(stage, target)
    atomic_write_json(paths.current, {"overlay_id": manifest.overlay_id})
    return manifest.overlay_id
