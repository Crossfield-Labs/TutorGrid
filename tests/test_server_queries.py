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


class ServerQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_trace_messages_and_errors_queries_return_payloads(self) -> None:
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
            session.context["planner_messages"] = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ]
            session.error = "boom"
            session.stop_reason = "failed"
            session.phase = "failed"
            manager.update(session)
            trace_store.append_session_event(
                session,
                event="orchestrator.session.summary",
                payload={"message": "done"},
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
                            "method": "orchestrator.session.trace",
                            "sessionId": session.session_id,
                            "params": {"limit": 20},
                        },
                        {
                            "type": "req",
                            "id": "req-2",
                            "method": "orchestrator.session.messages",
                            "sessionId": session.session_id,
                            "params": {"limit": 20},
                        },
                        {
                            "type": "req",
                            "id": "req-3",
                            "method": "orchestrator.session.errors",
                            "sessionId": session.session_id,
                            "params": {"limit": 20},
                        },
                    ]
                )
                await app.websocket_handler(websocket, "/ws/orchestrator", "")
            finally:
                app.session_manager = original_manager
                app.trace_store = original_trace_store

            self.assertEqual(websocket.sent[0]["event"], "orchestrator.session.trace")
            self.assertEqual(websocket.sent[0]["payload"]["items"][0]["event"], "orchestrator.session.summary")
            self.assertEqual(websocket.sent[1]["event"], "orchestrator.session.messages")
            self.assertEqual(websocket.sent[1]["payload"]["items"][0]["role"], "user")
            self.assertEqual(websocket.sent[2]["event"], "orchestrator.session.errors")
            self.assertEqual(websocket.sent[2]["payload"]["items"][0]["message"], "boom")


if __name__ == "__main__":
    unittest.main()
