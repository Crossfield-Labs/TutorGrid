from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.sessions.state import OrchestratorSessionState


class JsonlTraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _trace_path(self, session: OrchestratorSessionState) -> Path:
        trace_path_text = str(session.context.get("_trace_path") or "").strip()
        if trace_path_text:
            return Path(trace_path_text)
        self.root.mkdir(parents=True, exist_ok=True)
        trace_name = f"{session.task_id or 'task'}_{session.session_id[:8]}.jsonl"
        trace_path = self.root / trace_name
        session.context["_trace_path"] = str(trace_path)
        return trace_path

    def append_session_event(
        self,
        session: OrchestratorSessionState,
        *,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        trace_path = self._trace_path(session)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessionId": session.session_id,
            "taskId": session.task_id,
            "nodeId": session.node_id,
            "runner": session.runner,
            "event": event,
            "payload": payload or {},
        }
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list_session_history(self, session_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        if not self.root.exists():
            return entries
        for trace_path in sorted(self.root.glob("*.jsonl")):
            with trace_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("sessionId") != session_id:
                        continue
                    entries.append(entry)
        if not entries:
            return []
        entries.sort(key=lambda item: str(item.get("timestamp") or ""))
        if limit > 0:
            entries = entries[-limit:]
        return [
            {
                "seq": index + 1,
                "kind": self._normalize_event_kind(str(entry.get("event") or "")),
                "event": str(entry.get("event") or ""),
                "title": self._build_history_title(str(entry.get("event") or ""), entry.get("payload") or {}),
                "status": self._build_history_status(str(entry.get("event") or ""), entry.get("payload") or {}),
                "detail": self._build_history_detail(entry.get("payload") or {}),
                "createdAt": str(entry.get("timestamp") or ""),
            }
            for index, entry in enumerate(entries)
        ]

    @staticmethod
    def _normalize_event_kind(event: str) -> str:
        if ".phase" in event:
            return "phase"
        if ".summary" in event:
            return "summary"
        if ".worker" in event:
            return "worker"
        if ".snapshot" in event:
            return "snapshot"
        if ".subnode." in event:
            return "substep"
        if ".failed" in event:
            return "error"
        return "event"

    @staticmethod
    def _build_history_title(event: str, payload: dict[str, Any]) -> str:
        title = str(payload.get("title") or "").strip()
        if title:
            return title
        if ".subnode." in event:
            return str(payload.get("title") or payload.get("kind") or event.rsplit(".", 1)[-1]).strip() or "substep"
        if ".phase" in event:
            phase = str((payload.get("snapshot") or {}).get("phase") or payload.get("phase") or "").strip()
            return phase or "phase"
        if ".worker" in event:
            worker = str(payload.get("worker") or "").strip()
            return worker or "worker"
        return event.rsplit(".", 1)[-1] or event

    @staticmethod
    def _build_history_status(event: str, payload: dict[str, Any]) -> str:
        payload_status = str(payload.get("status") or "").strip()
        if payload_status:
            return payload_status
        if event.endswith(".failed"):
            return "failed"
        if event.endswith(".started"):
            return "started"
        if ".subnode." in event:
            return str(payload.get("status") or "completed")
        return "completed"

    @staticmethod
    def _build_history_detail(payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False)
        for key in ("detail", "message", "error", "result"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return json.dumps(payload, ensure_ascii=False)

