import json

from architecture_graph.indexer import index_corpus
from architecture_graph.overlay_snapshot import RationaleOverlayPaths, build_overlay_manifest, publish_rationale_overlay
from architecture_graph.project import ProjectPaths
from architecture_graph.rationale_resolver import resolve_rationales
from architecture_graph.snapshot import SnapshotReader
from conftest import git, ignore_architecture_graph
from helpers.rationale_overlay import capture_frozen_base


def test_context_overlay_preserves_base_rankings(architecture_repo) -> None:
    path = architecture_repo / "architecture" / "plan.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"decision_log": [
        {"title": f"ADR-{index}", "status": "accepted", "decision": f"Use boundary {index}", "context": f"Reason {index}", "consequences": [f"Effect {index}"]}
        for index in range(7)
    ]}))
    git(architecture_repo, "add", str(path.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "plan")
    ignore_architecture_graph(architecture_repo)
    indexed = index_corpus((path,))
    project = ProjectPaths.for_corpus(indexed.selection)
    reader = SnapshotReader.open(project)
    before = capture_frozen_base(reader)
    result = resolve_rationales(reader)
    publish_rationale_overlay(RationaleOverlayPaths.for_base(project, reader.snapshot_id), build_overlay_manifest(reader, result), result, reader)
    assert capture_frozen_base(reader) == before
    assert len(result.resolutions) == 7
    assert all(item["classification"] == "recognized_alias" for item in result.resolutions)
