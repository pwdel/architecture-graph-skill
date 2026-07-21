import json
from pathlib import Path

import pytest

import architecture_graph.snapshot as snapshot_module
from architecture_graph.canonical import (
    canonical_bytes,
    sha256_digest,
    source_revision_digest,
)
from architecture_graph.project import ProjectPaths
from architecture_graph.records import finalize_record
from architecture_graph.snapshot import (
    SnapshotBundle,
    SnapshotFinalizer,
    SnapshotReader,
    observe_existing_snapshot,
    publish_snapshot,
)


CONFIG_DIGEST = "sha256:" + "a" * 64
PIPELINE_PREIMAGE = {
    "schema_version": 1,
    "runtime": {
        "implementation": "CPython",
        "python_version": "3.12.0",
        "cache_tag": "cpython-312",
    },
    "files": {"adapter.py": "sha256:" + ("1" * 64)},
    "packages": {"PyYAML": "6.0.2", "jmespath": "1.1.0", "jsonlines": "4.0.0"},
}
PIPELINE_DIGEST = sha256_digest(canonical_bytes(PIPELINE_PREIMAGE))
CONTENT_DIGEST = "sha256:" + "c" * 64
EMPTY_REVIEWS_DIGEST = "sha256:" + "d" * 64
MATERIAL_DIGEST = "sha256:" + "e" * 64
SOURCE_REVISION_DIGEST = source_revision_digest([CONTENT_DIGEST])
INPUT_DIGEST = "sha256:" + "f" * 64


def bundle(path: str = "docs/adr/ADR-001.md") -> SnapshotBundle:
    source_id = f"source:{path}"
    derivation = finalize_record(
        {
            "id": "derivation:source-manifest",
            "kind": "derivation",
            "producer_kind": "deterministic",
            "method": "source_manifest",
            "tool": "architecture-graph",
            "tool_version": "0.1.0",
            "model": None,
            "model_version": None,
            "model_artifact_digest": None,
            "configuration_digest": CONFIG_DIGEST,
            "pipeline_digest": PIPELINE_DIGEST,
            "input_ids": [source_id],
            "output_kind": "source",
            "output_identity_key": source_id,
            "created_at": None,
        }
    )
    source = finalize_record(
        {
            "id": source_id,
            "kind": "source",
            "logical_source_id": f"logical-source:{path}",
            "path": path,
            "source_kind": "markdown",
            "document_role": "adr",
            "authority_class": "accepted_adr_or_active_standard",
            "authority_basis": "adr_status",
            "tracked": True,
            "git_blob": "fixture-blob",
            "content_hash": CONTENT_DIGEST,
            "decodable": True,
            "adr_metadata": {"id": "ADR-001", "status": "accepted"},
            "adapter_name": "markdown",
            "adapter_version": "v1",
            "parse_status": "complete",
            "warning_ids": [],
            "configuration_digest": CONFIG_DIGEST,
            "deterministic_pipeline_digest": PIPELINE_DIGEST,
            "derivation_ids": [derivation["id"]],
        }
    )
    return SnapshotBundle(
        snapshot_kind="deterministic",
        configuration_digest=CONFIG_DIGEST,
        schema_versions={"snapshot": 1, "records": 1},
        frozen_review_set_digest=EMPTY_REVIEWS_DIGEST,
        material_input_digest=MATERIAL_DIGEST,
        source_revision_digest=SOURCE_REVISION_DIGEST,
        deterministic_pipeline_digest=PIPELINE_DIGEST,
        pipeline_fingerprint=PIPELINE_PREIMAGE,
        input_digest=INPUT_DIGEST,
        analysis_parent_snapshot_id=None,
        parent_snapshot_id=None,
        base_deterministic_snapshot_id=None,
        records_by_type={"sources": [source], "derivations": [derivation]},
        report="# Ingestion\n\nOne source.\n",
    )


def observation(
    observed_at: str = "2026-07-19T10:00:00Z",
) -> dict[str, object]:
    return {
        "branch": "main",
        "commit": "a" * 40,
        "dirty_fingerprint": CONFIG_DIGEST,
        "observed_at": observed_at,
    }


def changed_bundle(original: SnapshotBundle, **changes: object) -> SnapshotBundle:
    return SnapshotBundle(**{**original.__dict__, **changes})


def test_snapshot_validation_rejects_invalid_semantic_record(tmp_path: Path) -> None:
    invalid_term = finalize_record({"id": "term:broken", "kind": "term"})
    invalid = changed_bundle(bundle(), schema_versions={"snapshot": 1, "records": 1, "semantic": 1}, records_by_type={**bundle().records_by_type, "terms": [invalid_term]})
    project = ProjectPaths.resolve(tmp_path, tmp_path / "memory")
    with pytest.raises(ValueError, match="semantic snapshot validation failed"):
        SnapshotFinalizer(project, invalid).validate()


@pytest.mark.parametrize("evidence_ids", ["evidence:missing", ["evidence:missing"]])
def test_snapshot_validation_rejects_malformed_or_dangling_semantic_references(tmp_path: Path, evidence_ids) -> None:
    term = finalize_record({"id": "term:broken", "kind": "term", "canonical_form": "broken", "observed_forms": ["broken"], "term_kind": "noun_phrase", "distinct_source_count": 1, "document_frequency": 1, "tfidf": 1.0, "discovery_signals": ["tfidf"], "evidence_ids": evidence_ids, "derivation_ids": ["derivation:source-manifest"]})
    invalid = changed_bundle(bundle(), schema_versions={"snapshot": 1, "records": 1, "semantic": 1}, records_by_type={**bundle().records_by_type, "terms": [term]})
    project = ProjectPaths.resolve(tmp_path, tmp_path / "memory")
    with pytest.raises(ValueError, match="semantic snapshot validation failed"):
        SnapshotFinalizer(project, invalid).validate()


def test_snapshot_validation_rejects_wrong_kind_semantic_reference(tmp_path: Path) -> None:
    term = finalize_record({"id": "term:broken", "kind": "term", "canonical_form": "broken", "observed_forms": ["broken"], "term_kind": "noun_phrase", "distinct_source_count": 1, "document_frequency": 1, "tfidf": 1.0, "discovery_signals": ["tfidf"], "evidence_ids": ["source:docs/adr/ADR-001.md"], "derivation_ids": ["derivation:source-manifest"]})
    invalid = changed_bundle(bundle(), schema_versions={"snapshot": 1, "records": 1, "semantic": 1}, records_by_type={**bundle().records_by_type, "terms": [term]})
    project = ProjectPaths.resolve(tmp_path, tmp_path / "memory")
    with pytest.raises(ValueError, match="wrong kind source"):
        SnapshotFinalizer(project, invalid).validate()


def reidentify_snapshot(
    snapshot_dir: Path, manifest: dict[str, object]
) -> tuple[str, Path]:
    manifest_core = {
        key: value for key, value in manifest.items() if key != "content_digest"
    }
    content_digest = sha256_digest(canonical_bytes(manifest_core))
    manifest["content_digest"] = content_digest
    (snapshot_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    digest_hex = content_digest.removeprefix("sha256:")
    target = snapshot_dir.parent / digest_hex
    snapshot_dir.rename(target)
    return f"{manifest['snapshot_kind']}:{digest_hex}", target


def test_observation_time_does_not_change_snapshot_identity(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    first = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    second = publish_snapshot(
        project,
        bundle(),
        observation("2026-07-19T11:00:00Z"),
        first.snapshot_id,
    )
    assert second.snapshot_id == first.snapshot_id
    assert second.snapshot_id.startswith("deterministic:")
    assert len(list((project.observations_path).read_text().splitlines())) == 2
    assert "2026-07-19" not in (first.snapshot_dir / "report.md").read_text()


def test_reader_defaults_to_current_and_is_read_only(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    reader = SnapshotReader.open(project)
    assert reader.snapshot_id == published.snapshot_id
    assert reader.get("sources", "source:docs/adr/ADR-001.md")["path"] == "docs/adr/ADR-001.md"


def test_stale_expected_current_cannot_replace_pointer(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    first = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    with pytest.raises(RuntimeError, match="current snapshot changed"):
        publish_snapshot(
            project,
            bundle("docs/adr/ADR-002.md"),
            observation("2026-07-19T11:00:00Z"),
            None,
        )
    assert SnapshotReader.open(project).snapshot_id == first.snapshot_id


def test_existing_digest_with_different_payload_is_fatal(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    (published.snapshot_dir / "sources.jsonl").write_text("corrupt\n")
    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, published.snapshot_id)
    with pytest.raises(ValueError, match="collision"):
        publish_snapshot(
            project,
            bundle(),
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_collision_rejects_unexpected_directories(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(project, bundle(), observation("2026-07-19T10:00:00Z"), None)
    (published.snapshot_dir / "unexpected").mkdir()
    with pytest.raises(ValueError, match="collision"):
        publish_snapshot(
            project,
            bundle(),
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_invalid_snapshot_id_and_unknown_payload_type_fail_closed(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    with pytest.raises(ValueError, match="invalid snapshot ID"):
        SnapshotReader.open(project, "deterministic:../../escape")
    invalid = bundle()
    invalid = SnapshotBundle(
        **{**invalid.__dict__, "records_by_type": {"soruces": []}}
    )
    with pytest.raises(ValueError, match="unknown snapshot record types"):
        publish_snapshot(project, invalid, observation("2026-07-19T10:00:00Z"), None)


def test_phase1_writer_rejects_layered_kinds_and_fingerprint_mismatch(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    layered = SnapshotBundle(**{**bundle().__dict__, "snapshot_kind": "reviewed"})
    with pytest.raises(ValueError, match="Phase 1 publishes deterministic"):
        publish_snapshot(
            project, layered, observation("2026-07-19T10:00:00Z"), None
        )

    mismatched = SnapshotBundle(
        **{
            **bundle().__dict__,
            "pipeline_fingerprint": {
                **PIPELINE_PREIMAGE,
                "packages": {"PyYAML": "different"},
            },
        }
    )
    with pytest.raises(ValueError, match="pipeline fingerprint"):
        publish_snapshot(
            project, mismatched, observation("2026-07-19T10:00:00Z"), None
        )


def test_false_source_revision_fails_validation_and_publication_without_pointer_change(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    current_before = project.current_path.read_bytes()
    wrong_digest = "sha256:" + ("8" * 64)
    assert wrong_digest != SOURCE_REVISION_DIGEST
    invalid = SnapshotBundle(
        **{**bundle().__dict__, "source_revision_digest": wrong_digest}
    )

    with pytest.raises(ValueError, match="source revision digest mismatch"):
        SnapshotFinalizer(project, invalid).validate()
    with pytest.raises(ValueError, match="source revision digest mismatch"):
        publish_snapshot(
            project,
            invalid,
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )

    assert project.current_path.read_bytes() == current_before
    assert SnapshotReader.open(project).snapshot_id == published.snapshot_id


def test_exact_duplicate_is_deduplicated_but_conflict_is_rejected(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    source = original.records_by_type["sources"][0]
    duplicate = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [source, source],
            },
        }
    )
    published = publish_snapshot(
        project, duplicate, observation("2026-07-19T10:00:00Z"), None
    )
    assert len(list(SnapshotReader.open(project).iter("sources"))) == 1

    conflicting_record = dict(source)
    conflicting_record["path"] = "docs/adr/ADR-002.md"
    conflicting = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [source, finalize_record(conflicting_record)]
            },
        }
    )
    with pytest.raises(ValueError, match="conflicting duplicate"):
        publish_snapshot(
            project,
            conflicting,
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )


def test_nfc_equivalent_record_ids_are_deduplicated_before_writing(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    decomposed = finalize_record(
        {"id": "term:Cafe\u0301", "kind": "term", "label": "Cafe\u0301"}
    )
    composed = finalize_record(
        {"id": "term:Caf\u00e9", "kind": "term", "label": "Caf\u00e9"}
    )
    with_equivalent_terms = changed_bundle(
        original,
        records_by_type={
            **original.records_by_type,
            "terms": [decomposed, composed],
        },
    )

    published = publish_snapshot(
        project,
        with_equivalent_terms,
        observation("2026-07-19T10:00:00Z"),
        None,
    )

    assert [record["id"] for record in SnapshotReader.open(project).iter("terms")] == [
        "term:Caf\u00e9"
    ]
    assert published.snapshot_dir.is_dir()


def test_broken_references_fail_before_publication(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    source = dict(original.records_by_type["sources"][0])
    source["warning_ids"] = ["warning:missing"]
    broken = SnapshotBundle(
        **{
            **original.__dict__,
            "records_by_type": {
                **original.records_by_type,
                "sources": [finalize_record(source)],
            },
        }
    )
    with pytest.raises(ValueError, match="broken reference"):
        publish_snapshot(
            project, broken, observation("2026-07-19T10:00:00Z"), None
        )
    assert not project.current_path.exists()


@pytest.mark.parametrize(
    "tamper", ["false_pipeline", "false_source_revision", "missing_payload"]
)
def test_reader_and_collision_reuse_reject_self_consistent_tampering(
    architecture_repo: Path, tmp_path: Path, tamper: str
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    manifest = json.loads(
        (published.snapshot_dir / "manifest.json").read_text(encoding="utf-8")
    )

    if tamper == "false_pipeline":
        manifest["deterministic_pipeline_digest"] = "sha256:" + ("7" * 64)
    elif tamper == "false_source_revision":
        manifest["source_revision_digest"] = "sha256:" + ("8" * 64)
    else:
        (published.snapshot_dir / "warnings.jsonl").unlink()
        manifest["payload_files"].pop("warnings.jsonl")

    snapshot_id, snapshot_dir = reidentify_snapshot(
        published.snapshot_dir, manifest
    )
    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, snapshot_id)
    with pytest.raises(ValueError, match="collision"):
        snapshot_module._verify_collision(snapshot_dir, manifest)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("unknown_type", "unknown snapshot record types"),
        ("malformed_digest", "invalid snapshot configuration_digest"),
        ("zero_schema", "schema_versions"),
        ("bad_schema", "schema_versions"),
        ("invalid_analysis_parent", "invalid analysis parent snapshot ID"),
        ("layered_parent", "layered parent fields"),
        ("layered_kind", "Phase 1 publishes deterministic"),
        ("fingerprint", "pipeline fingerprint"),
        ("source_revision", "source revision digest mismatch"),
        ("duplicate", "conflicting duplicate"),
        ("reference", "broken reference"),
        ("record_id", "ID must start with term:"),
    ],
)
def test_finalizer_and_publication_share_side_effect_free_validation(
    architecture_repo: Path,
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    original = bundle()
    changes: dict[str, object]
    if case == "unknown_type":
        changes = {"records_by_type": {"soruces": []}}
    elif case == "malformed_digest":
        changes = {"configuration_digest": "bad"}
    elif case == "zero_schema":
        changes = {"schema_versions": {"snapshot": 0, "records": 1}}
    elif case == "bad_schema":
        changes = {"schema_versions": {"snapshot": "1", "records": 1}}
    elif case == "invalid_analysis_parent":
        changes = {"analysis_parent_snapshot_id": "not-a-snapshot"}
    elif case == "layered_parent":
        changes = {"parent_snapshot_id": "deterministic:" + ("1" * 64)}
    elif case == "layered_kind":
        changes = {"snapshot_kind": "reviewed"}
    elif case == "fingerprint":
        changes = {
            "pipeline_fingerprint": {
                **PIPELINE_PREIMAGE,
                "packages": {"PyYAML": "different"},
            }
        }
    elif case == "source_revision":
        changes = {"source_revision_digest": "sha256:" + ("8" * 64)}
    elif case == "duplicate":
        source = original.records_by_type["sources"][0]
        conflicting = dict(source)
        conflicting["path"] = "docs/adr/ADR-002.md"
        changes = {
            "records_by_type": {
                **original.records_by_type,
                "sources": [source, finalize_record(conflicting)],
            }
        }
    elif case == "reference":
        source = dict(original.records_by_type["sources"][0])
        source["warning_ids"] = ["warning:missing"]
        changes = {
            "records_by_type": {
                **original.records_by_type,
                "sources": [finalize_record(source)],
            }
        }
    else:
        malformed = finalize_record({"id": "source:not-a-term", "kind": "term"})
        changes = {
            "records_by_type": {
                **original.records_by_type,
                "terms": [malformed],
            }
        }
    invalid = changed_bundle(original, **changes)

    with pytest.raises(ValueError, match=message):
        SnapshotFinalizer(project, invalid).validate()
    assert not project.project_dir.exists()

    with pytest.raises(ValueError, match=message):
        publish_snapshot(
            project, invalid, observation("2026-07-19T10:00:00Z"), None
        )
    assert not project.project_dir.exists()


def test_report_is_canonical_and_semantic_equivalents_share_identity(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    decomposed = changed_bundle(
        bundle(), report="# Cafe\u0301\r\n\rBody\r\n\n\n"
    )
    composed = changed_bundle(bundle(), report="# Caf\u00e9\n\nBody\n")

    first = publish_snapshot(
        project, decomposed, observation("2026-07-19T10:00:00Z"), None
    )
    second = publish_snapshot(
        project,
        composed,
        observation("2026-07-19T11:00:00Z"),
        first.snapshot_id,
    )

    assert (first.snapshot_dir / "report.md").read_bytes() == (
        "# Caf\u00e9\n\nBody\n".encode()
    )
    assert second.snapshot_id == first.snapshot_id
    assert second.reused is True


def test_observing_an_open_reader_revalidates_before_writing(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    reader = SnapshotReader.open(project)
    current_before = project.current_path.read_bytes()
    observations_before = project.observations_path.read_bytes()
    (published.snapshot_dir / "sources.jsonl").write_text("corrupt\n")

    with pytest.raises(ValueError, match="snapshot integrity"):
        observe_existing_snapshot(
            project,
            reader,
            observation("2026-07-19T11:00:00Z"),
            published.snapshot_id,
        )

    assert project.current_path.read_bytes() == current_before
    assert project.observations_path.read_bytes() == observations_before


def test_install_fsyncs_staging_and_snapshot_parents(
    architecture_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    synced: list[Path] = []
    real_sync = snapshot_module._sync

    def track_sync(path: Path) -> None:
        synced.append(path)
        real_sync(path)

    monkeypatch.setattr(snapshot_module, "_sync", track_sync)
    publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )

    assert synced[-2:] == [project.project_dir / ".staging", project.snapshots_dir]


@pytest.mark.parametrize(
    "tamper",
    ["extra_manifest_key", "noncanonical_jsonl", "duplicate_record", "report_crlf"],
)
def test_reader_rejects_self_consistent_noncanonical_snapshots(
    architecture_repo: Path, tmp_path: Path, tamper: str
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    manifest = json.loads(
        (published.snapshot_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if tamper == "extra_manifest_key":
        manifest["unexpected"] = True
    elif tamper == "report_crlf":
        report_path = published.snapshot_dir / "report.md"
        report_path.write_bytes(b"# Ingestion\r\n\r\nOne source.\r\n")
        manifest["payload_files"]["report.md"] = sha256_digest(
            report_path.read_bytes()
        )
    else:
        source_path = published.snapshot_dir / "sources.jsonl"
        record = json.loads(source_path.read_text(encoding="utf-8"))
        if tamper == "noncanonical_jsonl":
            source_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        else:
            source_path.write_bytes(canonical_bytes(record) * 2)
        manifest["payload_files"]["sources.jsonl"] = sha256_digest(
            source_path.read_bytes()
        )

    snapshot_id, _ = reidentify_snapshot(published.snapshot_dir, manifest)
    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, snapshot_id)


def test_reader_rejects_symlink_payload(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    external = project.project_dir / "external-empty.jsonl"
    external.write_bytes(b"")
    payload = published.snapshot_dir / "warnings.jsonl"
    payload.unlink()
    payload.symlink_to(external)

    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, published.snapshot_id)


def test_reader_rejects_noncanonical_manifest_bytes(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project, bundle(), observation("2026-07-19T10:00:00Z"), None
    )
    manifest_path = published.snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot integrity"):
        SnapshotReader.open(project, published.snapshot_id)


def test_invalid_observation_is_rejected_before_staging(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    with pytest.raises(ValueError, match="canonical UTC"):
        publish_snapshot(
            project,
            bundle(),
            observation(observed_at="2026-07-19T10:00:00+00:00"),
            None,
        )
    staging = project.project_dir / ".staging"
    assert not staging.exists() or list(staging.iterdir()) == []
    assert not project.current_path.exists()


def test_empty_observation_branch_is_rejected_before_staging(
    architecture_repo: Path, tmp_path: Path
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    invalid = {**observation(), "branch": ""}
    with pytest.raises(ValueError, match="nonempty string or null"):
        publish_snapshot(project, bundle(), invalid, None)
    staging = project.project_dir / ".staging"
    assert not staging.exists() or list(staging.iterdir()) == []


@pytest.mark.parametrize("commit", [None, "a" * 40, "b" * 64])
def test_observation_accepts_null_sha1_and_sha256_commits(
    architecture_repo: Path, tmp_path: Path, commit: str | None
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    published = publish_snapshot(
        project,
        bundle(),
        {**observation(), "commit": commit},
        None,
    )
    assert SnapshotReader.open(project).snapshot_id == published.snapshot_id
    observed = observe_existing_snapshot(
        project,
        SnapshotReader.open(project, published.snapshot_id),
        {
            **observation("2026-07-19T11:00:00Z"),
            "commit": commit,
        },
        published.snapshot_id,
    )
    assert observed.snapshot_id == published.snapshot_id


@pytest.mark.parametrize("commit", ["", "abc123", "A" * 40, "g" * 40])
def test_publish_rejects_invalid_commit_before_any_write(
    architecture_repo: Path, tmp_path: Path, commit: str
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    with pytest.raises(ValueError, match="lowercase SHA-1/SHA-256"):
        publish_snapshot(
            project,
            bundle(),
            {**observation(), "commit": commit},
            None,
        )
    assert not project.current_path.exists()
    assert not project.observations_path.exists()
    staging = project.project_dir / ".staging"
    assert not staging.exists() or list(staging.iterdir()) == []


def test_observe_rejects_invalid_commit_without_pointer_or_ledger_write(
    architecture_repo: Path, tmp_path: Path,
) -> None:
    project = ProjectPaths.resolve(architecture_repo, tmp_path / "memory")
    first = publish_snapshot(project, bundle(), observation(), None)
    reader = SnapshotReader.open(project, first.snapshot_id)
    pointer_before = project.current_path.read_bytes()
    ledger_before = project.observations_path.read_bytes()
    with pytest.raises(ValueError, match="lowercase SHA-1/SHA-256"):
        observe_existing_snapshot(
            project,
            reader,
            {**observation("2026-07-19T11:00:00Z"), "commit": "invalid"},
            first.snapshot_id,
        )
    assert project.current_path.read_bytes() == pointer_before
    assert project.observations_path.read_bytes() == ledger_before
    staging = project.project_dir / ".staging"
    assert not staging.exists() or list(staging.iterdir()) == []
