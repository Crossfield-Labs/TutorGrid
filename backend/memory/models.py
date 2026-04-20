from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryDocument:
    document_id: str
    session_id: str
    document_type: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    token_estimate: int = 0
    embedding: list[float] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class MemoryCompaction:
    session_id: str
    summary: str
    facts: list[str] = field(default_factory=list)
    source_item_count: int = 0
    updated_at: str = ""


@dataclass(slots=True)
class MemorySearchResult:
    document_id: str
    session_id: str
    document_type: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    updated_at: str = ""
