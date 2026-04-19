from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sessions.state import OrchestratorSessionState


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
