from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


@dataclass(slots=True)
class OrchestratorParams:
    runner: str = "orchestrator"
    workspace: str = ""
    task: str = ""
    goal: str = ""
    command: str = ""
    command_name: str = ""
    document_text: str = ""
    selection_text: str = ""
    execute: bool = False
    text: str = ""
    instruction: str = ""
    doc_id: str = ""
    input_content: str = ""
    input_kind: str = "reply"
    input_mode: str = "text"
    input_intent: str = "reply"
    target: str = ""
    session_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    limit: int = 200
    cursor: str = ""
    provider: str = ""
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    memory_enabled: bool = True
    memory_auto_compact: bool = True
    memory_compact_on_complete: bool = True
    memory_compact_on_failure: bool = True
    memory_retrieval_scope: str = ""
    memory_retrieval_strength: str = ""
    memory_cleanup_enabled: bool = True
    memory_cleanup_interval_hours: int = 24
    push_enabled: bool = True
    push_on_session_complete: bool = True
    push_on_session_failure: bool = False
    langsmith_enabled: bool = False
    langsmith_project: str = ""
    langsmith_api_key: str = ""
    langsmith_api_url: str = ""
    search_tavily_api_key: str = ""
    profile_level: str = ""
    profile_key: str = ""
    course_id: str = ""
    course_name: str = ""
    course_description: str = ""
    file_path: str = ""
    file_name: str = ""
    chunk_size: int = 900
    batch_size: int = 64
    user_id: str = ""
    knowledge_point: str = ""
    mastery: float = -1.0
    confidence: float = -1.0
    last_practiced_at: str = ""
    profile_data: dict[str, Any] = field(default_factory=dict)


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
            task_id=payload.get("taskId") or payload.get("task_id"),
            node_id=payload.get("nodeId") or payload.get("node_id"),
            session_id=payload.get("sessionId") or payload.get("session_id"),
            request_id=payload.get("id"),
            params=OrchestratorParams(
                runner=str(params.get("runner") or "orchestrator"),
                workspace=str(params.get("workspace") or ""),
                task=str(params.get("task") or ""),
                goal=str(params.get("goal") or ""),
                command=str(params.get("command") or ""),
                command_name=str(params.get("commandName") or ""),
                document_text=str(params.get("documentText") or ""),
                selection_text=str(params.get("selectionText") or ""),
                execute=bool(params.get("execute", False)),
                text=str(params.get("text") or ""),
                instruction=str(params.get("instruction") or ""),
                doc_id=str(params.get("docId") or params.get("doc_id") or ""),
                input_content=str(params.get("content") or params.get("inputContent") or ""),
                input_kind=str(params.get("kind") or params.get("inputKind") or "reply"),
                input_mode=str(params.get("inputMode") or "text"),
                input_intent=str(params.get("inputIntent") or "reply"),
                target=str(params.get("target") or ""),
                session_id=str(params.get("sessionId") or params.get("session_id") or ""),
                context=_coerce_dict(params.get("context")),
                limit=_coerce_int(params.get("limit"), 200),
                cursor=str(params.get("cursor") or ""),
                provider=str(params.get("provider") or ""),
                model=str(params.get("model") or ""),
                api_key=str(params.get("apiKey") or ""),
                api_base=str(params.get("apiBase") or ""),
                memory_enabled=bool(params.get("memoryEnabled", True)),
                memory_auto_compact=bool(params.get("memoryAutoCompact", True)),
                memory_compact_on_complete=bool(params.get("memoryCompactOnComplete", True)),
                memory_compact_on_failure=bool(params.get("memoryCompactOnFailure", True)),
                memory_retrieval_scope=str(params.get("memoryRetrievalScope") or ""),
                memory_retrieval_strength=str(params.get("memoryRetrievalStrength") or ""),
                memory_cleanup_enabled=bool(params.get("memoryCleanupEnabled", True)),
                memory_cleanup_interval_hours=_coerce_int(params.get("memoryCleanupIntervalHours"), 24),
                push_enabled=bool(params.get("pushEnabled", True)),
                push_on_session_complete=bool(params.get("pushOnSessionComplete", True)),
                push_on_session_failure=bool(params.get("pushOnSessionFailure", False)),
                langsmith_enabled=bool(params.get("langsmithEnabled", False)),
                langsmith_project=str(params.get("langsmithProject") or ""),
                langsmith_api_key=str(params.get("langsmithApiKey") or ""),
                langsmith_api_url=str(params.get("langsmithApiUrl") or ""),
                search_tavily_api_key=str(params.get("searchTavilyApiKey") or ""),
                profile_level=str(params.get("profileLevel") or ""),
                profile_key=str(params.get("profileKey") or ""),
                course_id=str(params.get("courseId") or ""),
                course_name=str(params.get("courseName") or ""),
                course_description=str(params.get("courseDescription") or ""),
                file_path=str(params.get("filePath") or ""),
                file_name=str(params.get("fileName") or ""),
                chunk_size=_coerce_int(params.get("chunkSize"), 900),
                batch_size=_coerce_int(params.get("batchSize"), 64),
                user_id=str(params.get("userId") or ""),
                knowledge_point=str(params.get("knowledgePoint") or ""),
                mastery=_coerce_float(params.get("mastery"), -1.0),
                confidence=_coerce_float(params.get("confidence"), -1.0),
                last_practiced_at=str(params.get("lastPracticedAt") or ""),
                profile_data=_coerce_dict(params.get("profileData")),
            ),
        )


def build_event(
    *,
    event: str,
    task_id: str | None,
    node_id: str | None,
    session_id: str | None,
    payload: dict[str, Any] | None = None,
    seq: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    frame = {
        "type": "event",
        "event": event,
        "taskId": task_id,
        "nodeId": node_id,
        "sessionId": session_id,
        "payload": payload or {},
    }
    if seq is not None:
        frame["seq"] = seq
    frame["timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()
    return frame
