import json

import pytest

from architecture_graph.cli import main
from architecture_graph.indexer import index_corpus
from conftest import ignore_architecture_graph


@pytest.mark.parametrize("command", ["terms", "neighbors", "decisions", "evidence", "explain", "report"])
def test_phase2_command_is_advertised(command) -> None:
    with pytest.raises(SystemExit) as raised:
        main([command, "--help"])
    assert raised.value.code == 0


def test_terms_cli_reads_published_snapshot(phase1_repository, capsys) -> None:
    ignore_architecture_graph(phase1_repository)
    index_corpus([phase1_repository])
    assert main(["terms", str(phase1_repository), "--limit", "3", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["items"]


def test_report_cli_honors_character_ceiling(phase1_repository, capsys) -> None:
    ignore_architecture_graph(phase1_repository)
    index_corpus([phase1_repository])
    assert main(["report", str(phase1_repository), "--max-chars", "3000"]) == 0
    assert len(capsys.readouterr().out) <= 3_000


def test_oversized_compact_record_has_typed_cli_error(phase1_repository, capsys) -> None:
    ignore_architecture_graph(phase1_repository)
    index_corpus([phase1_repository])
    assert main(["terms", str(phase1_repository), "--limit", "1", "--max-chars", "100", "--json"]) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "record_too_large"
