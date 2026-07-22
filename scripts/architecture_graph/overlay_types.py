from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from architecture_graph.records import Record


@dataclass(frozen=True)
class RationaleCoverage:
    decisions_examined: int
    explicit: int
    recognized_alias: int
    ambiguous: int
    missing: int
    warnings: int = 0

    def as_record(self) -> Record:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RationaleOverlayResult:
    resolutions: tuple[Record, ...]
    derivations: tuple[Record, ...]
    warnings: tuple[Record, ...]
    coverage: RationaleCoverage


@dataclass(frozen=True)
class RationaleOverlayManifest:
    overlay_id: str
    base_snapshot_id: str
    base_material_input_digest: str
    base_ranking_digest: str
    rule_version: str
    rule_digest: str
    content_digest: str
    coverage: RationaleCoverage

    def as_record(self) -> Record:
        return {
            "schema_version": 1,
            **{key: value for key, value in self.__dict__.items() if key != "coverage"},
            "coverage": self.coverage.as_record(),
        }
