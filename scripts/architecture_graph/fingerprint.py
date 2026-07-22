from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import json
import platform
import sys

from architecture_graph.canonical import canonical_bytes, sha256_digest


PACKAGES = ("jmespath", "jsonlines", "PyYAML")
OUTPUT_SUFFIXES = frozenset({".py", ".json", ".yaml", ".yml", ".md"})
FROZEN_BASE_FILES = Path(__file__).with_name("resources") / "base-pipeline-v0.3.1.json"
BASE_PIPELINE_VERSION = "0.3.1"


@dataclass(frozen=True)
class PipelineFingerprint:
    digest: str
    preimage: dict[str, object]


def pipeline_fingerprint(
    package_root: Path | None = None,
) -> PipelineFingerprint:
    if package_root is None:
        files = json.loads(FROZEN_BASE_FILES.read_text(encoding="utf-8"))
    else:
        root = package_root
        files = {
            path.relative_to(root).as_posix(): sha256_digest(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and path.suffix.casefold() in OUTPUT_SUFFIXES
            and "__pycache__" not in path.parts
        }
    packages: dict[str, str] = {}
    for package in PACKAGES:
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = "missing"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "runtime": {
            "implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "cache_tag": sys.implementation.cache_tag,
        },
        "files": files,
        "packages": packages,
    }
    return PipelineFingerprint(
        digest=sha256_digest(canonical_bytes(manifest)),
        preimage=manifest,
    )
