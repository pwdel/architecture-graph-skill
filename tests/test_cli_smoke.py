from importlib.metadata import version
from pathlib import Path
import subprocess

import pytest

from architecture_graph import __version__
from architecture_graph.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_package_version_has_one_source() -> None:
    assert __version__ == version("architecture-graph-skill")


def test_cli_prints_version(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_wrapper_prints_version_from_project_environment() -> None:
    result = subprocess.run(
        [str(ROOT / "bin" / "architecture-graph"), "--version"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == __version__
