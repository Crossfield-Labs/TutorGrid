from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CourseRecord:
    course_id: str
    name: str
    description: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class KnowledgeFileRecord:
    file_id: str
    course_id: str
    original_name: str
    stored_path: str
    file_ext: str
    parse_status: str
    parse_error: str
    source_type: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class KnowledgeJobRecord:
    job_id: str
    course_id: str
    file_id: str
    status: str
    progress: float
    message: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class KnowledgeChunkDraft:
    chunk_index: int
    content: str
    source_page: int
    source_section: str
    token_estimate: int
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
