from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SubstepRecord:
    kind: str
    title: str
    detail: str = ""
    status: str = "started"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeState:
    workspace: str
    goal: str
    session_id: str
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    substeps: list[SubstepRecord] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    worker_runs: list[dict[str, Any]] = field(default_factory=list)
    worker_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    final_answer: str = ""
