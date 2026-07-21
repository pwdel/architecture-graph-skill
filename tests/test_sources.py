from pathlib import Path
import subprocess

import pytest

from architecture_graph.canonical import (
    canonical_bytes,
    sha256_digest,
    source_revision_digest,
)
from architecture_graph.config import (
    ConfigurationPathError,
    ProjectConfig,
    configuration_digest,
    load_config,
)
from architecture_graph.fingerprint import pipeline_fingerprint
from architecture_graph.project import (
    ProjectPaths,
    RepositoryStateError,
    capture_git_observation,
    normalize_remote,
)
from architecture_graph.sources import discover_sources, material_input_digest


def test_defaults_select_only_tracked_architecture_files(
    architecture_repo: Path,
) -> None:
    config = load_config(architecture_repo)
    inputs = discover_sources(architecture_repo, config)
    assert [item.relative_path for item in inputs] == ["docs/adr/ADR-001.md"]
    assert inputs[0].tracked is True
    assert inputs[0].git_blob is not None


def test_explicit_supported_file_bypasses_default_include(
    architecture_repo: Path,
) -> None:
    from conftest import git

    plan = architecture_repo / "lib" / "design" / "design-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text('{"decision":"backend owns truth"}')
    git(architecture_repo, "add", "lib/design/design-plan.json")
    git(architecture_repo, "commit", "-m", "add design plan")
    selected = discover_sources(
        architecture_repo, ProjectConfig(), ("lib/design/design-plan.json",)
    )
    assert [item.relative_path for item in selected] == [
        "lib/design/design-plan.json"
    ]


def test_focused_directory_applies_default_selection(
    architecture_repo: Path,
) -> None:
    selected = discover_sources(architecture_repo, ProjectConfig(), ("docs",))
    assert [item.relative_path for item in selected] == ["docs/adr/ADR-001.md"]


def test_explicit_unsupported_file_fails(architecture_repo: Path) -> None:
    readme = architecture_repo / "README.bin"
    readme.write_bytes(b"binary")
    with pytest.raises(ValueError, match="unsupported explicit source"):
        discover_sources(architecture_repo, ProjectConfig(), ("README.bin",))


def test_git_blob_hashes_the_selected_working_tree_bytes(
    architecture_repo: Path,
) -> None:
    path = architecture_repo / "docs" / "adr" / "ADR-001.md"
    path.write_text(path.read_text() + "\nDirty but selected.\n")
    item = discover_sources(architecture_repo, load_config(architecture_repo))[0]
    index_blob = subprocess.run(
        ["git", "-C", str(architecture_repo), "rev-parse", ":docs/adr/ADR-001.md"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    working_blob = subprocess.run(
        ["git", "-C", str(architecture_repo), "hash-object", "--stdin"],
        check=True,
        input=path.read_bytes(),
        capture_output=True,
    ).stdout.decode("ascii").strip()
    assert item.git_blob == working_blob
    assert item.git_blob != index_blob


def test_only_configured_untracked_files_enter_manifest(architecture_repo: Path) -> None:
    (architecture_repo / "docs" / "adr" / "draft.md").write_text("# Draft\n")
    (architecture_repo / "docs" / "adr" / "secret.md").write_text("# Secret\n")
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nuntracked:\n  - docs/adr/draft.md\n"
    )
    inputs = discover_sources(architecture_repo, load_config(architecture_repo))
    assert [item.relative_path for item in inputs] == [
        "docs/adr/ADR-001.md",
        "docs/adr/draft.md",
    ]
    assert inputs[1].tracked is False


def test_tracked_file_cannot_be_reclassified_through_untracked(
    architecture_repo: Path,
) -> None:
    from conftest import git

    tracked = architecture_repo / "notes.md"
    tracked.write_text("# Tracked but outside default includes\n")
    git(architecture_repo, "add", "notes.md")
    git(architecture_repo, "commit", "-m", "add tracked note")
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nuntracked:\n  - notes.md\n"
    )
    with pytest.raises(ValueError, match="configured untracked source is tracked"):
        discover_sources(architecture_repo, load_config(architecture_repo))


def test_redundant_untracked_entry_keeps_selected_tracked_provenance(
    architecture_repo: Path,
) -> None:
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nuntracked:\n  - docs/adr/ADR-001.md\n"
    )
    item = discover_sources(architecture_repo, load_config(architecture_repo))[0]
    assert item.tracked is True
    assert item.git_blob is not None


def test_plain_text_requires_an_explicit_pattern(architecture_repo: Path) -> None:
    notes = architecture_repo / "docs" / "architecture" / "notes.txt"
    notes.parent.mkdir(parents=True)
    notes.write_text("Checkout depends on Orders.\n")
    from conftest import git

    git(architecture_repo, "add", "docs/architecture/notes.txt")
    git(architecture_repo, "commit", "-m", "add notes")
    assert all(
        item.relative_path != "docs/architecture/notes.txt"
        for item in discover_sources(architecture_repo, load_config(architecture_repo))
    )
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nplaintext:\n  - docs/architecture/notes.txt\n"
    )
    assert any(
        item.relative_path == "docs/architecture/notes.txt"
        for item in discover_sources(architecture_repo, load_config(architecture_repo))
    )


def test_deleted_tracked_source_is_removed_from_the_manifest(
    architecture_repo: Path,
) -> None:
    (architecture_repo / "docs" / "adr" / "ADR-001.md").unlink()
    assert discover_sources(architecture_repo, load_config(architecture_repo)) == []


def test_untracked_plain_text_still_requires_plaintext_selection(
    architecture_repo: Path,
) -> None:
    note = architecture_repo / "docs" / "adr" / "local.txt"
    note.write_text("Local notes.\n")
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nuntracked:\n  - docs/adr/local.txt\n"
    )
    with pytest.raises(ValueError, match="plaintext"):
        discover_sources(architecture_repo, load_config(architecture_repo))


def test_dirty_content_and_pipeline_code_change_material_digest(
    architecture_repo: Path, tmp_path: Path
) -> None:
    config = load_config(architecture_repo)
    first_inputs = discover_sources(architecture_repo, config)
    pipeline_root = tmp_path / "pipeline"
    pipeline_root.mkdir()
    module = pipeline_root / "stage.py"
    module.write_text("RULE = 1\n")
    first_pipeline = pipeline_fingerprint(pipeline_root)
    assert sha256_digest(canonical_bytes(first_pipeline.preimage)) == first_pipeline.digest
    assert set(first_pipeline.preimage) == {
        "schema_version",
        "runtime",
        "files",
        "packages",
    }
    first = material_input_digest(first_inputs, config, first_pipeline.digest)

    (architecture_repo / "docs" / "adr" / "ADR-001.md").write_text("# changed\n")
    second_inputs = discover_sources(architecture_repo, config)
    second = material_input_digest(second_inputs, config, first_pipeline.digest)
    assert second != first

    module.write_text("RULE = 2\n")
    second_pipeline = pipeline_fingerprint(pipeline_root)
    assert material_input_digest(second_inputs, config, second_pipeline.digest) != second


def test_material_input_digest_is_independent_of_caller_order(
    architecture_repo: Path,
) -> None:
    from architecture_graph.sources import SourceInput

    config = load_config(architecture_repo)
    first = discover_sources(architecture_repo, config)[0]
    second = SourceInput(
        **{
            **first.__dict__,
            "relative_path": "docs/adr/ADR-002.md",
            "absolute_path": architecture_repo / "docs" / "adr" / "ADR-002.md",
        }
    )
    pipeline_digest = "sha256:" + ("a" * 64)

    assert material_input_digest(
        [first, second], config, pipeline_digest
    ) == material_input_digest([second, first], config, pipeline_digest)


def test_material_input_digest_rejects_duplicate_relative_paths(
    architecture_repo: Path,
) -> None:
    config = load_config(architecture_repo)
    item = discover_sources(architecture_repo, config)[0]

    with pytest.raises(ValueError, match="duplicate source path"):
        material_input_digest([item, item], config, "sha256:" + ("a" * 64))


def test_source_revision_digest_uses_unique_content_hashes_only(
    architecture_repo: Path,
) -> None:
    from architecture_graph.sources import SourceInput

    inputs = discover_sources(architecture_repo, load_config(architecture_repo))
    assert source_revision_digest(item.content_hash for item in inputs) == sha256_digest(
        canonical_bytes(sorted({item.content_hash for item in inputs}))
    )
    duplicate = SourceInput(
        **{
            **inputs[0].__dict__,
            "relative_path": "docs/adr/copy.md",
            "absolute_path": architecture_repo / "docs" / "adr" / "copy.md",
        }
    )
    assert source_revision_digest(
        item.content_hash for item in [*inputs, duplicate]
    ) == source_revision_digest(item.content_hash for item in inputs)
    changed = SourceInput(
        **{
            **inputs[0].__dict__,
            "content_hash": "sha256:" + ("f" * 64),
        }
    )
    assert source_revision_digest(
        item.content_hash for item in [changed]
    ) != source_revision_digest(item.content_hash for item in inputs)


def test_memory_root_precedence(architecture_repo: Path, tmp_path: Path, monkeypatch) -> None:
    codex_home = tmp_path / "codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    paths = ProjectPaths.resolve(architecture_repo)
    assert paths.projects_root == codex_home / "memories" / "architecture-graph" / "projects"
    assert paths.project_dir.parent == paths.projects_root


@pytest.mark.parametrize(
    "contents",
    [
        "schema_version: true\n",
        "include: docs/architecture\n",
        "untracked: [../outside.md]\n",
        "review_authorities: {architect: .nan}\n",
        "source_roles: []\n",
    ],
)
def test_invalid_configuration_types_and_paths_fail_closed(
    architecture_repo: Path, contents: str
) -> None:
    (architecture_repo / ".architecture-graph.yaml").write_text(contents)
    with pytest.raises(ValueError):
        load_config(architecture_repo)


def test_configuration_digest_covers_materialized_defaults(
    architecture_repo: Path,
) -> None:
    default = load_config(architecture_repo)
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\nexclude: [docs/architecture/archive/**]\n"
    )
    assert configuration_digest(load_config(architecture_repo)) != configuration_digest(
        default
    )


def test_duplicate_configuration_keys_fail_closed(architecture_repo: Path) -> None:
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\ninclude: [docs/adr/*.md]\ninclude: [architecture/**]\n"
    )
    with pytest.raises(ValueError, match="duplicate configuration key"):
        load_config(architecture_repo)


def test_declared_aliases_are_normalized_and_affect_the_digest(
    architecture_repo: Path,
) -> None:
    default = load_config(architecture_repo)
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\naliases:\n  Checkout API: checkout-service\n"
    )
    configured = load_config(architecture_repo)
    assert configured.aliases == {"checkout api": "checkout-service"}
    assert configuration_digest(configured) != configuration_digest(default)


def test_alias_targets_are_terminal(architecture_repo: Path) -> None:
    (architecture_repo / ".architecture-graph.yaml").write_text(
        "schema_version: 1\naliases:\n  checkout api: checkout\n  checkout: commerce\n"
    )
    with pytest.raises(ValueError, match="terminal canonical identifiers"):
        load_config(architecture_repo)


def test_remote_normalization_removes_transport_spelling_noise() -> None:
    assert normalize_remote("git@GitHub.com:Org/Repo.git") == normalize_remote(
        "ssh://git@github.com/Org/Repo/"
    )


def test_explicit_config_path_is_root_relative(architecture_repo: Path) -> None:
    nested = architecture_repo / "config" / "custom.yaml"
    nested.parent.mkdir()
    nested.write_text("schema_version: 1\n")
    assert load_config(architecture_repo, Path("config/custom.yaml")) == ProjectConfig()


def test_missing_explicit_config_does_not_fall_back(architecture_repo: Path) -> None:
    with pytest.raises(ConfigurationPathError, match="configuration file not found"):
        load_config(architecture_repo, Path("missing.yaml"))


def test_dirty_fingerprint_changes_for_repeated_same_path_edits(
    architecture_repo: Path,
) -> None:
    tracked = architecture_repo / "docs" / "adr" / "ADR-001.md"
    tracked.write_text("first dirty value\n")
    first = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    tracked.write_text("second dirty value\n")
    second = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    assert second != first


def test_dirty_fingerprint_tracks_repeated_staged_bytes_independently(
    architecture_repo: Path,
) -> None:
    from conftest import git

    tracked = architecture_repo / "docs" / "adr" / "ADR-001.md"
    relative = "docs/adr/ADR-001.md"
    tracked.write_text("first staged value\n")
    git(architecture_repo, "add", relative)
    tracked.write_text("fixed worktree value\n")
    assert git(architecture_repo, "status", "--short", relative).startswith("MM ")
    first = capture_git_observation(architecture_repo)["dirty_fingerprint"]

    tracked.write_text("second staged value\n")
    git(architecture_repo, "add", relative)
    tracked.write_text("fixed worktree value\n")
    assert git(architecture_repo, "status", "--short", relative).startswith("MM ")
    second = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    assert second != first


def test_dirty_fingerprint_changes_for_repeated_untracked_edits(
    architecture_repo: Path,
) -> None:
    untracked = architecture_repo / "same-path.md"
    untracked.write_text("first\n")
    first = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    untracked.write_text("second\n")
    second = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    assert second != first


def test_dirty_fingerprint_hashes_symlink_bytes_not_target_bytes(
    architecture_repo: Path,
) -> None:
    link = architecture_repo / "untracked-link"
    link.symlink_to("first-target")
    first = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    link.unlink()
    link.symlink_to("second-target")
    second = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    assert second != first


def test_dirty_fingerprint_distinguishes_regular_file_from_same_byte_symlink(
    architecture_repo: Path,
) -> None:
    path = architecture_repo / "same-kind-path"
    path.write_bytes(b"same-target")
    path.chmod(0o777)
    regular = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    path.unlink()
    path.symlink_to("same-target")
    symlink = capture_git_observation(architecture_repo)["dirty_fingerprint"]
    assert symlink != regular


def test_dirty_path_digest_rejects_unsupported_file_type(tmp_path: Path) -> None:
    from architecture_graph.project import _path_digest

    with pytest.raises(RepositoryStateError, match="unsupported dirty path type"):
        _path_digest(tmp_path)


def test_malformed_git_status_path_fails_as_repository_state(
    architecture_repo: Path, monkeypatch
) -> None:
    from architecture_graph.project import _dirty_preimage_once

    monkeypatch.setattr(
        "architecture_graph.project._git_bytes_checked",
        lambda *args, **kwargs: b"? \xff\0",
    )
    with pytest.raises(RepositoryStateError, match="non-UTF-8 path"):
        _dirty_preimage_once(architecture_repo)


def test_project_id_rejects_non_utf8_remote_as_repository_state(
    architecture_repo: Path, monkeypatch
) -> None:
    from architecture_graph.project import project_id

    monkeypatch.setattr(
        "architecture_graph.project.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=b"\xff", stderr=b""
        ),
    )
    with pytest.raises(RepositoryStateError, match="non-UTF-8 identity output"):
        project_id(architecture_repo)


@pytest.mark.parametrize("failure", ["executable", "git"])
def test_project_id_maps_git_failures_to_repository_state(
    architecture_repo: Path, monkeypatch, failure: str
) -> None:
    from architecture_graph.project import project_id

    def fail(*args, **kwargs):
        if failure == "executable":
            raise PermissionError("cannot execute Git")
        return subprocess.CompletedProcess(args[0], 2, stdout=b"", stderr=b"failed")

    monkeypatch.setattr("architecture_graph.project.subprocess.run", fail)
    with pytest.raises(RepositoryStateError, match="Git .*failed|could not run"):
        project_id(architecture_repo)


def test_git_observation_rejects_head_change_during_dirty_capture(
    architecture_repo: Path, monkeypatch
) -> None:
    from conftest import git
    from architecture_graph import project as project_module

    real_capture = project_module._stable_dirty_preimage

    def advance_head(root: Path):
        readme = root / "README.md"
        readme.write_text(readme.read_text() + "concurrent commit\n")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "advance head during observation")
        return real_capture(root)

    monkeypatch.setattr(
        "architecture_graph.project._stable_dirty_preimage", advance_head
    )
    with pytest.raises(RepositoryStateError, match="HEAD changed"):
        capture_git_observation(architecture_repo)
