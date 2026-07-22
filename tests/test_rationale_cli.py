import json

from architecture_graph.cli import main
from architecture_graph.indexer import index_corpus
from conftest import ignore_architecture_graph


def test_rationale_build_status_and_find(phase1_repository, capsys) -> None:
    ignore_architecture_graph(phase1_repository)
    indexed = index_corpus([phase1_repository])
    root = str(phase1_repository)
    assert main(["rationale", "build", root, "--corpus", indexed.selection.corpus_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["overlay_id"].startswith("rationale-overlay:")
    assert main(["rationale", "status", root, "--corpus", indexed.selection.corpus_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["coverage"]["decisions_examined"] >= 1
    assert main(["rationale", "find", root, "--corpus", indexed.selection.corpus_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["items"]


def test_missing_rationale_overlay_has_typed_error(phase1_repository, capsys) -> None:
    ignore_architecture_graph(phase1_repository)
    indexed = index_corpus([phase1_repository])
    assert main(["rationale", "status", str(phase1_repository), "--corpus", indexed.selection.corpus_id, "--json"]) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "overlay_not_found"
