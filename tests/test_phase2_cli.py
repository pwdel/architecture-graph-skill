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
