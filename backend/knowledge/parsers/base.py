from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class ParsedBlock:
    text: str
    section: str = ""
    page: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    title: str
    blocks: list[ParsedBlock]
    metadata: dict[str, Any] = field(default_factory=dict)


class Parser(Protocol):
    def parse(self, file_path: Path) -> ParsedDocument:
        raise NotImplementedError

