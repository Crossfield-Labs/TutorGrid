from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class OrchestratorParams:
    runner: str = "orchestrator"
    workspace: str = ""
    task: str = ""
    goal: str = ""
    command: str = ""
    text: str = ""
    input_mode: str = "text"
    input_intent: str = "reply"
    target: str = ""
    limit: int = 200
    cursor: str = ""


@dataclass(slots=True)
class OrchestratorRequest:
    type: str
    method: str
    task_id: str | None = None
    node_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    params: OrchestratorParams = field(default_factory=OrchestratorParams)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OrchestratorRequest":
        params = payload.get("params") or {}
        return cls(
            type=str(payload.get("type") or ""),
            method=str(payload.get("method") or ""),
            task_id=payload.get("taskId"),
            node_id=payload.get("nodeId"),
            session_id=payload.get("sessionId"),
            request_id=payload.get("id"),
            params=OrchestratorParams(
                runner=str(params.get("runner") or "orchestrator"),
                workspace=str(params.get("workspace") or ""),
                task=str(params.get("task") or ""),
                goal=str(params.get("goal") or ""),
                command=str(params.get("command") or ""),
                text=str(params.get("text") or ""),
                input_mode=str(params.get("inputMode") or "text"),
                input_intent=str(params.get("inputIntent") or "reply"),
                target=str(params.get("target") or ""),
                limit=_coerce_int(params.get("limit"), 200),
                cursor=str(params.get("cursor") or ""),
            ),
        )


def build_event(
    *,
    event: str,
    task_id: str | None,
    node_id: str | None,
    session_id: str | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "event",
        "event": event,
        "taskId": task_id,
        "nodeId": node_id,
        "sessionId": session_id,
        "payload": payload or {},
    }

