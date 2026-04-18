from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkerArtifact:
    path: str
    change_type: str
    size: int | None = None


@dataclass(slots=True)
class WorkerProgressEvent:
    phase: str
    message: str
    detail: str = ""
    raw_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkerSessionRef:
    worker: str
    session_id: str
    session_key: str = "primary"
    mode: str = "new"
    continued_from: str = ""


@dataclass(slots=True)
class WorkerControlRef:
    worker: str
    session_id: str
    task_id: str = ""
    can_interrupt: bool = False
    interrupt: Callable[[], Awaitable[dict[str, Any]]] | None = None
    get_runtime_info: Callable[[], Awaitable[dict[str, Any]]] | None = None


@dataclass(slots=True)
class WorkerResult:
    worker: str
    success: bool
    summary: str
    output: str
    artifacts: list[WorkerArtifact] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    session: WorkerSessionRef | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(
        self,
        *,
        include_raw_events: bool = True,
        output_limit: int | None = None,
    ) -> dict[str, Any]:
        output = self.output
        if output_limit is not None and len(output) > output_limit:
            output = output[:output_limit] + "\n...[truncated]"
        record = {
            "worker": self.worker,
            "success": self.success,
            "summary": self.summary,
            "output": output,
            "error": self.error,
            "artifacts": [
                {"path": artifact.path, "change_type": artifact.change_type, "size": artifact.size}
                for artifact in self.artifacts
            ],
        }
        if self.session is not None:
            record["session"] = {
                "worker": self.session.worker,
                "session_id": self.session.session_id,
                "session_key": self.session.session_key,
                "mode": self.session.mode,
                "continued_from": self.session.continued_from,
            }
        if self.metadata:
            record["metadata"] = dict(self.metadata)
        if include_raw_events:
            record["raw_events"] = list(self.raw_events)
        return record

    def to_json(self, *, include_raw_events: bool = False) -> str:
        return json.dumps(
            self.to_record(include_raw_events=include_raw_events, output_limit=2500 if not include_raw_events else None),
            ensure_ascii=False,
        )
