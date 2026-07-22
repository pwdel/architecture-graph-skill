from pathlib import Path

from architecture_graph.overlay_snapshot import RationaleOverlayPaths
from test_phase2_golden import _index


def test_overlay_paths_are_separate_from_base_snapshots(tmp_path: Path) -> None:
    reader = _index(tmp_path / "repo")
    paths = RationaleOverlayPaths.for_base(reader.project, reader.snapshot_id)
    assert reader.project.snapshots_dir not in paths.root.parents
    assert paths.root == reader.project.project_dir / "overlays" / "rationale" / reader.snapshot_id.replace(":", "-")
