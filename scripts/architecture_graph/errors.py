from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureGraphError(RuntimeError):
    code: str
    message: str
    path: str | None = None

    def __str__(self) -> str:
        return self.message

    def as_json(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "path": self.path,
            }
        }
