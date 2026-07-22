from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

from architecture_graph.canonical import atomic_write_json, canonical_bytes, sha256_digest, stable_id
from architecture_graph.jsonl_store import iter_records, write_records
from architecture_graph.overlay_contract import validate_rationale_overlay
from architecture_graph.overlay_types import RationaleOverlayManifest, RationaleOverlayResult
from architecture_graph.project import ProjectLock, ProjectPaths
from architecture_graph.records import validate_record
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.rationale_rules import rationale_rule_digest


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
    def open(
        cls,
        paths: RationaleOverlayPaths,
        overlay_id: str | None = None,
        *,
        base: SnapshotReader | None = None,
    ) -> "RationaleOverlayReader":
        if overlay_id is None:
            if not paths.current.is_file():
                raise FileNotFoundError("rationale overlay not found")
            try:
                current = json.loads(paths.current.read_text())
                overlay_id = current["overlay_id"]
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise ValueError("rationale overlay validation failed: invalid current pointer") from error
        directory = paths.snapshots / overlay_id.replace(":", "-")
        manifest = json.loads((directory / "MANIFEST.json").read_text())
        if manifest.get("overlay_id") != overlay_id:
            raise ValueError("overlay incompatible: manifest identity mismatch")
        reader = cls(overlay_id, directory, manifest)
        resolutions = tuple(reader.iter_resolutions())
        derivations = tuple(reader.iter_derivations())
        warnings = tuple(reader.iter_warnings())
        content_digest = sha256_digest(
            canonical_bytes(
                {
                    "resolutions": list(resolutions),
                    "derivations": list(derivations),
                    "warnings": list(warnings),
                    "coverage": manifest.get("coverage"),
                }
            )
        )
        expected_id = stable_id(
            "rationale-overlay",
            manifest.get("base_snapshot_id"),
            manifest.get("base_ranking_digest"),
            content_digest,
            manifest.get("rule_version"),
        )
        if manifest.get("content_digest") != content_digest or expected_id != overlay_id:
            raise ValueError("overlay incompatible: content identity mismatch")
        if base is not None:
            reader.validate_base(base)
            issues = validate_rationale_overlay(resolutions, base, derivations)
            if issues:
                raise ValueError(
                    f"rationale overlay validation failed: {issues[0].field}: {issues[0].message}"
                )
        return reader

    def iter_resolutions(self):
        return iter_records(self.directory / "rationale-resolutions.jsonl")

    def iter_derivations(self):
        return iter_records(self.directory / "derivations.jsonl")

    def iter_warnings(self):
        return iter_records(self.directory / "warnings.jsonl")

    def validate_base(self, base: SnapshotReader) -> None:
        ranking_digest = sha256_digest((base.snapshot_dir / "rankings.jsonl").read_bytes())
        expected = (
            self.manifest.get("base_snapshot_id"),
            self.manifest.get("base_material_input_digest"),
            self.manifest.get("base_ranking_digest"),
        )
        actual = (
            base.snapshot_id,
            base.manifest.get("material_input_digest"),
            ranking_digest,
        )
        if expected != actual or self.manifest.get("rule_digest") != rationale_rule_digest():
            raise ValueError("overlay incompatible: base snapshot or ranking digest differs")


def _assert_base_unchanged(base: SnapshotReader, manifest: RationaleOverlayManifest) -> None:
    try:
        current = SnapshotReader.open(base.project, base.snapshot_id)
    except (OSError, ValueError) as error:
        raise ValueError("base snapshot changed") from error
    ranking_digest = sha256_digest((current.snapshot_dir / "rankings.jsonl").read_bytes())
    if (
        manifest.base_snapshot_id != current.snapshot_id
        or manifest.base_material_input_digest != current.manifest["material_input_digest"]
        or manifest.base_ranking_digest != ranking_digest
    ):
        raise ValueError("base snapshot changed")


def publish_rationale_overlay(paths: RationaleOverlayPaths, manifest: RationaleOverlayManifest, result: RationaleOverlayResult, base: SnapshotReader) -> str:
    issues = validate_rationale_overlay(result.resolutions, base, result.derivations)
    if issues:
        raise ValueError(f"rationale overlay validation failed: {issues[0].field}: {issues[0].message}")
    for record in (*result.derivations, *result.warnings):
        validate_record(record)
    actual_counts = {
        name: sum(1 for item in result.resolutions if item.get("classification") == name)
        for name in ("explicit", "recognized_alias", "ambiguous", "missing")
    }
    if result.coverage.as_record() != {
        "decisions_examined": len(result.resolutions),
        **actual_counts,
        "warnings": len(result.warnings),
    }:
        raise ValueError("rationale overlay validation failed: coverage: does not match records")
    _assert_base_unchanged(base, manifest)
    if manifest != build_overlay_manifest(base, result):
        raise ValueError("rationale overlay validation failed: manifest: does not match content")
    with ProjectLock(base.project.lock_path):
        _assert_base_unchanged(base, manifest)
        paths.snapshots.mkdir(parents=True, exist_ok=True)
        target = paths.snapshots / manifest.overlay_id.replace(":", "-")
        if not target.exists():
            stage = Path(tempfile.mkdtemp(prefix=".rationale-", dir=paths.snapshots))
            write_records(stage / "rationale-resolutions.jsonl", result.resolutions)
            write_records(stage / "derivations.jsonl", result.derivations)
            write_records(stage / "warnings.jsonl", result.warnings)
            atomic_write_json(stage / "MANIFEST.json", manifest.as_record())
            _assert_base_unchanged(base, manifest)
            os.replace(stage, target)
        RationaleOverlayReader.open(paths, manifest.overlay_id, base=base)
        _assert_base_unchanged(base, manifest)
        atomic_write_json(paths.current, {"overlay_id": manifest.overlay_id})
    return manifest.overlay_id


def build_overlay_manifest(base: SnapshotReader, result: RationaleOverlayResult) -> RationaleOverlayManifest:
    ranking_digest = sha256_digest((base.snapshot_dir / "rankings.jsonl").read_bytes())
    content = canonical_bytes(
        {
            "resolutions": list(result.resolutions),
            "derivations": list(result.derivations),
            "warnings": list(result.warnings),
            "coverage": result.coverage.as_record(),
        }
    )
    content_digest = sha256_digest(content)
    overlay_id = stable_id("rationale-overlay", base.snapshot_id, ranking_digest, content_digest, "rationale-rules-v1")
    return RationaleOverlayManifest(
        overlay_id=overlay_id,
        base_snapshot_id=base.snapshot_id,
        base_material_input_digest=str(base.manifest["material_input_digest"]),
        base_ranking_digest=ranking_digest,
        rule_version="rationale-rules-v1",
        rule_digest=rationale_rule_digest(),
        content_digest=content_digest,
        coverage=result.coverage,
    )
