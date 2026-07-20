from __future__ import annotations

from dataclasses import dataclass

from architecture_graph.records import Record


@dataclass(frozen=True)
class IngestionContext:
    configuration_digest: str
    pipeline_digest: str
    tool_version: str
    max_segment_chars: int = 8_000


@dataclass(frozen=True)
class IngestionResult:
    segments: tuple[Record, ...] = ()
    evidence: tuple[Record, ...] = ()
    derivations: tuple[Record, ...] = ()
    warnings: tuple[Record, ...] = ()

    def merge(self, other: "IngestionResult") -> "IngestionResult":
        return IngestionResult(
            segments=(*self.segments, *other.segments),
            evidence=(*self.evidence, *other.evidence),
            derivations=(*self.derivations, *other.derivations),
            warnings=(*self.warnings, *other.warnings),
        )
