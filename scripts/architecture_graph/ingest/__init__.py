from __future__ import annotations

from dataclasses import dataclass
import re

from architecture_graph.records import Record


@dataclass(frozen=True)
class IngestionContext:
    configuration_digest: str
    pipeline_digest: str
    tool_version: str
    max_segment_chars: int = 8_000

    def __post_init__(self) -> None:
        digest_pattern = re.compile(r"sha256:[0-9a-f]{64}")
        for field_name in ("configuration_digest", "pipeline_digest"):
            value = getattr(self, field_name)
            if type(value) is not str or digest_pattern.fullmatch(value) is None:
                raise ValueError(
                    f"{field_name} must be lowercase sha256:<64 hex>"
                )
        if type(self.tool_version) is not str or not self.tool_version.strip():
            raise ValueError("tool_version must be a non-empty string")
        if (
            type(self.max_segment_chars) is not int
            or self.max_segment_chars < 256
        ):
            raise ValueError("max_segment_chars must be an integer >= 256")


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
