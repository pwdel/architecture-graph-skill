from pathlib import Path
import shutil
import subprocess

import pytest


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ignore_architecture_graph(repo: Path) -> None:
    ignore = repo / ".gitignore"
    prior = ignore.read_text() if ignore.exists() else ""
    if ".architecture-graph/\n" not in prior:
        ignore.write_text(prior + ".architecture-graph/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore architecture graph memory")


@pytest.fixture
def architecture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "ADR-001.md").write_text(
        "# ADR-001 Events\n\nStatus: Accepted\n\n## Decision\nCheckout must publish OrderPlaced.\n"
    )
    (repo / "README.md").write_text("not architecture input\n")
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "add", "docs/adr/ADR-001.md", "README.md")
    git(repo, "commit", "-m", "fixture")
    return repo


@pytest.fixture
def phase1_repository(tmp_path: Path) -> Path:
    fixture = Path(__file__).parent / "fixtures" / "phase1_repo"
    repo = tmp_path / "phase1-repo"
    shutil.copytree(fixture, repo)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "phase1 fixture")
    return repo
