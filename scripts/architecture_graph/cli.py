from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from architecture_graph import __version__
from architecture_graph.canonical import canonical_dumps
from architecture_graph.indexer import index_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="architecture-graph")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    index = commands.add_parser("index", help="build a deterministic snapshot")
    index.add_argument("root", type=Path)
    index.add_argument("--memory-root", type=Path)
    index.add_argument("--config", type=Path)
    index.add_argument("--observed-at", help=argparse.SUPPRESS)
    index.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "index":
            result = index_repository(
                args.root,
                memory_root=args.memory_root,
                config_path=args.config,
                observed_at=args.observed_at,
            )
            payload = result.as_json()
            if args.json:
                print(canonical_dumps(payload))
            else:
                print(
                    f"Indexed {payload['source_count']} sources into "
                    f"{payload['snapshot_id']}"
                )
            return 0
    except OSError as error:
        print(
            "architecture-graph: filesystem operation failed "
            f"({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    except RuntimeError as error:
        print(f"architecture-graph: {error}", file=sys.stderr)
        return 2
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
