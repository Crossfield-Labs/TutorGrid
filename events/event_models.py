from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProgressEvent:
    message: str
    progress: float | None = None
