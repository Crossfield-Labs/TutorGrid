from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.server import app
from backend.sessions.manager import SessionManager
from backend.storage.jsonl_trace import JsonlTraceStore
from backend.storage.sqlite_store import SQLiteSessionStore


class _FakeWebSocket:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self._messages = [json.dumps(item, ensure_ascii=False) for item in messages]
        self.sent: list[dict[str, object]] = []
        self.request_headers: dict[str, str] = {}

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, *, code: int, reason: str) -> None:
        raise AssertionError(f"unexpected close: {code} {reason}")


class ServerTipTapTests(unittest.IsolatedAsyncioTestCase):
    async def test_tiptap_execute_queues_followup_for_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = SQLiteSessionStore(root / "orchestrator.sqlite3")
            manager = SessionManager(store=store)
            trace_store = JsonlTraceStore(root / "trace")
            session = manager.create(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace=".",
                task="inspect",
                goal="inspect",
            )

            original_manager = app.session_manager
            original_trace_store = app.trace_store
            app.session_manager = manager
            app.trace_store = trace_store
            try:
                websocket = _FakeWebSocket(
                    [
                        {
                            "type": "req",
                            "id": "req-1",
                            "method": "orchestrator.tiptap.command",
                            "sessionId": session.session_id,
                            "params": {
                                "commandName": "explain-selection",
                                "selectionText": "马拉车算法",
                                "execute": True,
                            },
                        }
                    ]
                )
                await app.websocket_handler(websocket, "/ws/orchestrator", "")
            finally:
                app.session_manager = original_manager
                app.trace_store = original_trace_store

            self.assertEqual(websocket.sent[0]["event"], "orchestrator.tiptap.command")
            self.assertEqual(websocket.sent[0]["payload"]["mode"], "followup")
            self.assertEqual(len(manager.get(session.session_id).followups), 1)


if __name__ == "__main__":
    unittest.main()
