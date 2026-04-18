from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from orchestrator.workers.models import WorkerProgressEvent


class ClaudeSdkBridge:
    @staticmethod
    def build_hook_event(
        *,
        hook_event: str,
        message: str,
        tool_name: str = "",
        status: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkerProgressEvent:
        merged_metadata = dict(metadata or {})
        merged_metadata.update({"hook_event": hook_event, "tool_name": tool_name, "hook_status": status})
        return WorkerProgressEvent(
            phase="worker_hook",
            message=message,
            raw_type=f"hook:{hook_event}",
            metadata=merged_metadata,
        )

    @staticmethod
    def build_summary_event(
        *,
        phase: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerProgressEvent:
        return WorkerProgressEvent(phase=phase, message=message, raw_type=phase, metadata=dict(metadata or {}))

    @staticmethod
    def to_record(message: Any) -> dict[str, Any]:
        if is_dataclass(message):
            payload = asdict(message)
        elif isinstance(message, dict):
            payload = dict(message)
        else:
            payload = {"value": repr(message)}
        payload["_type"] = type(message).__name__
        return payload

    @staticmethod
    def extract_session_id(message: Any) -> str:
        return str(getattr(message, "session_id", "") or "").strip()

    @staticmethod
    def extract_text(message: Any) -> str:
        if type(message).__name__ == "AssistantMessage":
            parts: list[str] = []
            for block in getattr(message, "content", []) or []:
                if type(block).__name__ == "TextBlock":
                    text = str(getattr(block, "text", "") or "").strip()
                    if text:
                        parts.append(text)
            return "\n".join(parts).strip()
        if type(message).__name__ == "ResultMessage":
            return str(getattr(message, "result", "") or "").strip()
        if type(message).__name__ == "TaskNotificationMessage":
            return str(getattr(message, "summary", "") or "").strip()
        return ""

    @staticmethod
    def to_progress_events(message: Any) -> list[WorkerProgressEvent]:
        message_type = type(message).__name__
        raw_record = ClaudeSdkBridge.to_record(message)
        session_id = ClaudeSdkBridge.extract_session_id(message)
        session_suffix = f" ({session_id[:8]})" if session_id else ""

        if message_type == "SystemMessage":
            return [
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"claude started a session{session_suffix}",
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        if message_type == "TaskStartedMessage":
            description = str(getattr(message, "description", "") or "claude started a background task").strip()
            metadata = {
                **raw_record,
                "task_id": getattr(message, "task_id", None),
                "task_type": getattr(message, "task_type", None),
            }
            return [
                WorkerProgressEvent(
                    phase="worker_step",
                    message=f"claude started task: {description[:200]}",
                    raw_type=message_type,
                    metadata=metadata,
                )
            ]

        if message_type == "TaskProgressMessage":
            description = str(getattr(message, "description", "") or "claude is working").strip()
            metadata = {
                **raw_record,
                "task_id": getattr(message, "task_id", None),
                "last_tool_name": getattr(message, "last_tool_name", None),
            }
            return [
                WorkerProgressEvent(
                    phase="worker_step",
                    message=f"claude progress: {description[:200]}",
                    raw_type=message_type,
                    metadata=metadata,
                )
            ]

        if message_type == "TaskNotificationMessage":
            status = str(getattr(message, "status", "") or "completed").strip()
            summary = str(getattr(message, "summary", "") or "").strip()
            return [
                WorkerProgressEvent(
                    phase="worker_step",
                    message=f"claude task {status}: {summary[:200] or 'background task update'}",
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        if message_type == "AssistantMessage":
            events: list[WorkerProgressEvent] = []
            for block in getattr(message, "content", []) or []:
                block_type = type(block).__name__
                if block_type == "TextBlock":
                    text = str(getattr(block, "text", "") or "").strip()
                    if text:
                        events.append(
                            WorkerProgressEvent(
                                phase="worker_text",
                                message=f"claude says: {text[:200]}",
                                detail=text[:1200],
                                raw_type=message_type,
                                metadata=raw_record,
                            )
                        )
                elif block_type == "ToolUseBlock":
                    tool_name = str(getattr(block, "name", "") or "tool").strip()
                    tool_input = getattr(block, "input", None)
                    events.append(
                        WorkerProgressEvent(
                            phase="worker_tool",
                            message=f"claude is using {tool_name}",
                            detail=str(tool_input)[:800],
                            raw_type=message_type,
                            metadata={
                                **raw_record,
                                "tool_name": tool_name,
                                "tool_use_id": getattr(block, "id", None),
                                "tool_input": tool_input,
                            },
                        )
                    )
                elif block_type == "ToolResultBlock":
                    content = getattr(block, "content", None)
                    events.append(
                        WorkerProgressEvent(
                            phase="worker_tool",
                            message="claude received a tool result",
                            detail=str(content)[:800],
                            raw_type=message_type,
                            metadata={
                                **raw_record,
                                "tool_use_id": getattr(block, "tool_use_id", None),
                                "is_error": getattr(block, "is_error", None),
                            },
                        )
                    )
            if events:
                return events
            return [
                WorkerProgressEvent(
                    phase="worker_text",
                    message="claude produced a response",
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        if message_type == "ResultMessage":
            result = str(getattr(message, "result", "") or "").strip()
            errors = getattr(message, "errors", None)
            detail = result[:1200] if result else ""
            if errors:
                detail = (detail + "\n" if detail else "") + "\n".join(str(item) for item in errors[:5])
            return [
                WorkerProgressEvent(
                    phase="worker_step",
                    message=f"claude finished the current turn{session_suffix}",
                    detail=detail,
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        if message_type == "StreamEvent":
            event = getattr(message, "event", None)
            event_type = ""
            if isinstance(event, dict):
                event_type = str(event.get("type") or event.get("event") or "").strip()
            return [
                WorkerProgressEvent(
                    phase="worker_event",
                    message=f"claude stream event: {event_type or 'stream'}",
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        if message_type == "RateLimitEvent":
            return [
                WorkerProgressEvent(
                    phase="worker_event",
                    message="claude reported current rate limit information",
                    raw_type=message_type,
                    metadata=raw_record,
                )
            ]

        return [
            WorkerProgressEvent(
                phase="worker_event",
                message=f"claude event: {message_type}",
                raw_type=message_type,
                metadata=raw_record,
            )
        ]
