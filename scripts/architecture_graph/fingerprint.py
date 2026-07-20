from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import sys

from architecture_graph.canonical import canonical_bytes, sha256_digest


PACKAGES = ("jmespath", "jsonlines", "PyYAML")
OUTPUT_SUFFIXES = frozenset({".py", ".json", ".yaml", ".yml", ".md"})


@dataclass(frozen=True)
class PipelineFingerprint:
    digest: str
    preimage: dict[str, object]


def pipeline_fingerprint(
    package_root: Path | None = None,
) -> PipelineFingerprint:
    root = package_root or Path(__file__).resolve().parent
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
