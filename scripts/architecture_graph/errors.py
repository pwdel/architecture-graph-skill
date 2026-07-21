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


class RecordTooLargeError(ValueError):
    def __init__(self, record_id: str, max_chars: int, minimum_chars: int) -> None:
        self.record_id = record_id
        self.max_chars = max_chars
        self.minimum_chars = minimum_chars
        super().__init__(
            f"record {record_id} requires at least {minimum_chars} characters; "
            f"max_chars is {max_chars}"
        )
