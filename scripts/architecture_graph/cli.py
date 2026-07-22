from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys

from architecture_graph import __version__
from architecture_graph.canonical import canonical_dumps
from architecture_graph.capabilities import capability_record
from architecture_graph.corpus import CorpusSelection, MemoryNotIgnoredError
from architecture_graph.config import ConfigurationPathError
from architecture_graph.errors import ArchitectureGraphError, RecordTooLargeError
from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths, RepositoryStateError
from architecture_graph.query import (
    find_snapshot_records,
    get_snapshot_record,
    memory_status,
    render_query_envelope,
)
from architecture_graph.report import ReportLimits, build_report, render_report_text
from architecture_graph.semantic_queries import decisions_query, evidence_query, explain_query, neighbors_query, terms_query
from architecture_graph.records import RECORD_KIND_BY_TYPE
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.overlay_snapshot import RationaleOverlayPaths, RationaleOverlayReader, build_overlay_manifest, publish_rationale_overlay
from architecture_graph.rationale_resolver import resolve_rationales
from architecture_graph.overlay_queries import rationale_find_query


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="architecture-graph")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")

    capabilities = commands.add_parser(
        "capabilities", help="show implemented phases and commands"
    )
    capabilities.add_argument("--json", action="store_true")

    index = commands.add_parser("index", help="build a deterministic snapshot")
    index.add_argument("paths", type=Path, nargs="+")
    index.add_argument("--memory-root", type=Path)
    index.add_argument("--config", type=Path)
    index.add_argument("--observed-at", help=argparse.SUPPRESS)
    index.add_argument("--json", action="store_true")

    memory = commands.add_parser("memory", help="inspect project memory")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    status = memory_commands.add_parser("status")
    status.add_argument("paths", type=Path, nargs="+")
    status.add_argument("--memory-root", type=Path)
    status.add_argument("--config", type=Path)
    status.add_argument("--fields")
    status.add_argument("--max-chars", type=int, default=12_000)
    status.add_argument("--json", action="store_true")

    get = commands.add_parser("get", help="get one exact record")
    get.add_argument("record_type", choices=tuple(RECORD_KIND_BY_TYPE))
    get.add_argument("record_id")
    _query_arguments(get)

    find = commands.add_parser("find", help="scan one record file with bounds")
    find.add_argument("record_type", choices=tuple(RECORD_KIND_BY_TYPE))
    _query_arguments(find)
    find.add_argument("--where", action="append", default=[])
    find.add_argument("--contains")
    find.add_argument("--limit", type=int, default=20)
    find.add_argument("--cursor")
    find.add_argument("--jmespath")

    for name in ("terms", "neighbors", "decisions", "evidence", "explain", "report"):
        command = commands.add_parser(name)
        command.add_argument("root", type=Path)
        command.add_argument("--memory-root", type=Path)
        command.add_argument("--corpus")
        command.add_argument("--snapshot")
        command.add_argument("--max-chars", type=int, default=12_000)
        command.add_argument("--json", action="store_true")
        if name != "report":
            command.add_argument("--fields")
            command.add_argument("--limit", type=int, default=20)
            command.add_argument("--cursor")
    commands.choices["neighbors"].add_argument("--node", required=True)
    commands.choices["neighbors"].add_argument("--depth", type=int, default=1)
    commands.choices["decisions"].add_argument("--score", choices=("navigation", "criticality", "review_priority", "extraction_confidence", "corroboration", "completeness"), default="navigation")
    commands.choices["evidence"].add_argument("--for", dest="record_id", required=True)
    commands.choices["explain"].add_argument("--id", dest="record_id", required=True)
    for name in ("decisions", "explain", "report"):
        commands.choices[name].add_argument("--base-only", action="store_true")
    rationale = commands.add_parser("rationale", help="build and inspect rationale overlays")
    rationale_commands = rationale.add_subparsers(dest="rationale_command", required=True)
    for name in ("build", "status", "find"):
        command = rationale_commands.add_parser(name)
        command.add_argument("root", type=Path)
        command.add_argument("--memory-root", type=Path)
        command.add_argument("--corpus")
        command.add_argument("--snapshot")
        command.add_argument("--json", action="store_true")
        command.add_argument("--max-chars", type=int, default=12_000)
    rationale_commands.choices["find"].add_argument("--classification", choices=("explicit", "recognized_alias", "ambiguous", "missing"))
    rationale_commands.choices["find"].add_argument("--limit", type=int, default=20)
    rationale_commands.choices["find"].add_argument("--cursor")
    return parser


def _query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--memory-root", type=Path)
    parser.add_argument("--corpus")
    parser.add_argument("--snapshot")
    parser.add_argument("--fields")
    parser.add_argument("--max-chars", type=int, default=12_000)
    parser.add_argument("--json", action="store_true")


def _fields(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    fields = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not fields:
        raise ValueError("fields must contain at least one name")
    return fields


def _filters(raw: Sequence[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(f"invalid --where value: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError("filter key cannot be empty")
        result[key] = value
    return result


def _select_project(
    repository: Path, corpus_id: str | None, memory_root: Path | None
) -> ProjectPaths:
    root = repository.resolve()
    configured = os.environ.get("ARCHITECTURE_GRAPH_MEMORY_ROOT")
    base = (
        memory_root.resolve()
        if memory_root
        else Path(configured).resolve()
        if configured
        else root / ".architecture-graph"
    )
    corpora = base / "corpora"
    metadata_files = sorted(corpora.glob("*/CORPUS.json")) if corpora.is_dir() else []
    if memory_root is not None and corpus_id is None and not metadata_files:
        legacy = ProjectPaths.resolve(root, memory_root)
        if legacy.current_path.is_file():
            return legacy
    if corpus_id is None:
        if not metadata_files:
            raise FileNotFoundError("architecture graph corpus not found")
        if len(metadata_files) != 1:
            choices = ", ".join(
                f"{path.parent.name} ({', '.join(json.loads(path.read_text())['inputs'])})"
                for path in metadata_files
            )
            raise ValueError(f"multiple corpora found; select --corpus from: {choices}")
        selected = metadata_files[0]
    else:
        selected = corpora / corpus_id / "CORPUS.json"
        if not selected.is_file():
            raise FileNotFoundError(f"corpus not found: {corpus_id}")
    raw = json.loads(selected.read_text(encoding="utf-8"))
    if set(raw) != {"schema_version", "corpus_id", "repository", "inputs"}:
        raise ValueError("corpus metadata has invalid shape")
    if raw["schema_version"] != 1 or raw["corpus_id"] != selected.parent.name:
        raise ValueError("corpus metadata identity mismatch")
    if Path(str(raw["repository"])).resolve() != root:
        raise ValueError("corpus metadata belongs to a different repository")
    selection = CorpusSelection(root, tuple(raw["inputs"]), str(raw["corpus_id"]))
    return ProjectPaths.for_corpus(selection, memory_root)


def _print_error(error: ArchitectureGraphError, as_json: bool) -> None:
    if as_json:
        sys.stderr.write(canonical_dumps(error.as_json()) + "\n")
    else:
        suffix = "" if error.path is None else f" [{error.path}]"
        sys.stderr.write(f"architecture-graph: {error.message}{suffix}\n")


def _as_expected(error: Exception) -> ArchitectureGraphError:
    if isinstance(error, RecordTooLargeError):
        return ArchitectureGraphError("record_too_large", str(error), error.record_id)
    if isinstance(error, MemoryNotIgnoredError):
        ignored_path = str(error).split("add ", 1)[-1].split(" to ", 1)[0]
        return ArchitectureGraphError(
            "memory_not_ignored", str(error), ignored_path
        )
    if isinstance(error, ConfigurationPathError):
        return ArchitectureGraphError("invalid_configuration", str(error))
    if isinstance(error, FileNotFoundError):
        message = str(error)
        if "rationale overlay" in message:
            code = "overlay_not_found"
        else:
            code = "snapshot_not_found" if "snapshot" in message else "corpus_not_found"
        return ArchitectureGraphError(code, message)
    if isinstance(error, PermissionError):
        filename = getattr(error, "filename", None)
        path = None if filename is None else Path(filename).name
        return ArchitectureGraphError(
            "permission_denied", "permission denied during filesystem operation", path
        )
    if isinstance(error, RepositoryStateError):
        return ArchitectureGraphError("repository_state", str(error))
    if isinstance(error, KeyError):
        return ArchitectureGraphError("record_not_found", str(error))
    message = str(error)
    mappings = (
        ("cursor", "invalid_cursor"),
        ("JMESPath", "invalid_jmespath"),
        ("multiple corpora", "ambiguous_corpus"),
        ("corpus metadata", "invalid_corpus_metadata"),
        ("snapshot integrity", "snapshot_integrity"),
        ("current snapshot changed", "publication_conflict"),
        ("same Git worktree", "cross_repository_inputs"),
        ("unsupported explicit source", "unsupported_input"),
        ("overlay incompatible", "overlay_incompatible"),
        ("base snapshot changed", "overlay_stale"),
        ("rationale overlay validation failed", "overlay_validation_failed"),
    )
    for token, code in mappings:
        if token in message:
            return ArchitectureGraphError(code, message)
    return ArchitectureGraphError("invalid_request", str(error))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    as_json = bool(getattr(args, "json", False))
    try:
        if args.command == "capabilities":
            payload = capability_record()
            if as_json:
                print(canonical_dumps(payload))
            else:
                print("Architecture Graph phase1, phase2")
                print("Commands: " + ", ".join(payload["commands"]))
            return 0
        if args.command == "index":
            result = index_corpus(
                args.paths,
                memory_root=args.memory_root,
                config_path=args.config,
                observed_at=args.observed_at,
            )
            payload = result.as_json()
            if as_json:
                print(canonical_dumps(payload))
            else:
                print(
                    f"Indexed {payload['source_count']} sources into "
                    f"{payload['snapshot_id']} (corpus {payload['corpus_id']})"
                )
            return 0
        if args.command == "rationale":
            project = _select_project(args.root, args.corpus, args.memory_root)
            reader = SnapshotReader.open(project, args.snapshot)
            paths = RationaleOverlayPaths.for_base(project, reader.snapshot_id)
            if args.rationale_command == "build":
                result = resolve_rationales(reader)
                manifest = build_overlay_manifest(reader, result)
                overlay_id = publish_rationale_overlay(paths, manifest, result, reader)
                payload = {"overlay_id": overlay_id, "base_snapshot_id": reader.snapshot_id, "coverage": result.coverage.as_record()}
            else:
                overlay = RationaleOverlayReader.open(paths, base=reader)
                records = list(overlay.iter_resolutions())
                if args.rationale_command == "find":
                    result = rationale_find_query(
                        overlay,
                        classification=args.classification,
                        limit=args.limit,
                        max_chars=args.max_chars,
                        cursor=args.cursor,
                    )
                    sys.stdout.write(render_query_envelope(result, "json" if as_json else "markdown"))
                    return 0
                else:
                    counts = {name: sum(1 for item in records if item.get("classification") == name) for name in ("explicit", "recognized_alias", "ambiguous", "missing")}
                    payload = {"overlay_id": overlay.overlay_id, "base_snapshot_id": overlay.manifest["base_snapshot_id"], "coverage": {"decisions_examined": len(records), **counts}}
            rendered = canonical_dumps(payload) + "\n"
            if len(rendered) > args.max_chars: raise ValueError("rationale response exceeds max_chars")
            sys.stdout.write(rendered)
            return 0
        if args.command == "memory":
            result = memory_status(
                args.paths,
                memory_root=args.memory_root,
                config_path=args.config,
                fields=_fields(args.fields),
                max_chars=args.max_chars,
            )
            sys.stdout.write(render_query_envelope(result, "json" if as_json else "markdown"))
            return 0
        if args.command in {"terms", "neighbors", "decisions", "evidence", "explain", "report"}:
            project = _select_project(args.root, args.corpus, args.memory_root)
            reader = SnapshotReader.open(project, args.snapshot)
            base_only = bool(getattr(args, "base_only", False))
            overlay_reader = None
            if not base_only and args.command in {"decisions", "explain", "report"}:
                overlay_paths = RationaleOverlayPaths.for_base(project, reader.snapshot_id)
                if overlay_paths.current.is_file():
                    overlay_reader = RationaleOverlayReader.open(overlay_paths, base=reader)
            if args.command == "report":
                report = build_report(reader, limits=ReportLimits(max_chars=args.max_chars), overlay_reader=overlay_reader, base_only=base_only)
                if as_json:
                    assertions = [{key: value for key, value in item.items() if key != "evidence_ids"} for item in report.assertions]
                    payload = {"coverage": report.coverage, "assertions": assertions}
                    while len(canonical_dumps(payload)) + 1 > args.max_chars and assertions:
                        assertions.pop()
                    if len(canonical_dumps(payload)) + 1 > args.max_chars:
                        raise ValueError("report max_chars is too small for coverage metadata")
                    print(canonical_dumps(payload))
                else:
                    sys.stdout.write(render_report_text(report))
                return 0
            common = {"fields": _fields(args.fields), "limit": args.limit, "max_chars": args.max_chars, "cursor": args.cursor}
            if args.command == "terms": result = terms_query(reader, **common)
            elif args.command == "neighbors": result = neighbors_query(reader, node_id=args.node, depth=args.depth, **common)
            elif args.command == "decisions": result = decisions_query(reader, score=args.score, overlay_reader=overlay_reader, base_only=base_only, **common)
            elif args.command == "evidence": result = evidence_query(reader, record_id=args.record_id, **common)
            else: result = explain_query(reader, record_id=args.record_id, overlay_reader=overlay_reader, base_only=base_only, **common)
            sys.stdout.write(render_query_envelope(result, "json" if as_json else "markdown"))
            return 0
        project = _select_project(args.repo, args.corpus, args.memory_root)
        reader = SnapshotReader.open(project, args.snapshot)
        if args.command == "get":
            result = get_snapshot_record(
                reader,
                args.record_type,
                args.record_id,
                fields=_fields(args.fields),
                max_chars=args.max_chars,
            )
        else:
            result = find_snapshot_records(
                reader,
                args.record_type,
                filters=_filters(args.where),
                contains=args.contains,
                fields=_fields(args.fields),
                limit=args.limit,
                max_chars=args.max_chars,
                cursor=args.cursor,
                expression=args.jmespath,
            )
        sys.stdout.write(render_query_envelope(result, "json" if as_json else "markdown"))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        _print_error(_as_expected(error), as_json)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
