from __future__ import annotations

import asyncio
import json
import unittest
from collections import defaultdict
from pathlib import Path

from backend.memory.service import MemoryService
from backend.runners.base import AwaitUserCallback, BaseRunner, MessageEventCallback, ProgressCallback, SubstepCallback
from backend.server import app as server_app
from backend.sessions.manager import SessionManager
from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore
from backend.storage.sqlite_store import SQLiteSessionStore
from harness.models import HarnessTaskSpec
from harness.runner import run_task, run_task_files
from tests.temp_paths import workspace_temp_dir
from websockets.legacy.server import serve


class _HarnessRunnerStub(BaseRunner):
    def __init__(self) -> None:
        self._emit_substep: SubstepCallback | None = None
        self._emit_message_event: MessageEventCallback | None = None

    def set_event_callbacks(
        self,
        *,
        emit_substep: SubstepCallback | None = None,
        emit_message_event: MessageEventCallback | None = None,
    ) -> None:
        self._emit_substep = emit_substep
        self._emit_message_event = emit_message_event

    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        await emit_progress("Harness runner active", 0.2)
        if self._emit_substep is not None:
            await self._emit_substep("tool", "Prepare", "completed", "ready")
        if self._emit_message_event is not None:
            payload = {
                "messageId": f"{session.session_id}:assistant:1:1",
                "role": "assistant",
                "contentType": "text/markdown",
                "phase": "planning",
            }
            await self._emit_message_event("started", payload)
            await self._emit_message_event("delta", {**payload, "delta": "hello "})
            await self._emit_message_event("delta", {**payload, "delta": "world"})
            await self._emit_message_event("completed", {**payload, "content": "hello world", "finishReason": "stop"})
        session.set_latest_summary("harness summary")
        return "hello world"


class _HarnessRouter:
    def __init__(self) -> None:
        self._runner = _HarnessRunnerStub()

    def get(self, runner_name: str) -> BaseRunner:
        return self._runner


class HarnessRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._temp_dir = workspace_temp_dir("harness-")
        root = self._temp_dir.__enter__()
        self._originals = {
            "session_manager": server_app.session_manager,
            "trace_store": server_app.trace_store,
            "memory_service": server_app.memory_service,
            "runner_router": server_app.runner_router,
            "session_waiters": server_app.session_waiters,
            "session_tasks": server_app.session_tasks,
            "session_subscribers": server_app.session_subscribers,
            "subscriber_event_namespaces": server_app.subscriber_event_namespaces,
        }
        server_app.session_manager = SessionManager(SQLiteSessionStore(root / "session.sqlite3"))
        server_app.trace_store = JsonlTraceStore(root / "trace")
        server_app.memory_service = MemoryService(path=root / "memory.sqlite3")
        server_app.runner_router = _HarnessRouter()
        server_app.session_waiters = {}
        server_app.session_tasks = {}
        server_app.session_subscribers = defaultdict(set)
        server_app.subscriber_event_namespaces = {}
        self._server = await serve(
            lambda websocket, path: server_app.websocket_handler(websocket, path, ""),
            "127.0.0.1",
            0,
        )
        self._port = self._server.sockets[0].getsockname()[1]
        self._root = root

    async def asyncTearDown(self) -> None:
        self._server.close()
        await self._server.wait_closed()
        for task in list(server_app.session_tasks.values()):
            task.cancel()
        for task in list(server_app.session_tasks.values()):
            try:
                await task
            except BaseException:
                pass
        server_app.session_manager = self._originals["session_manager"]
        server_app.trace_store = self._originals["trace_store"]
        server_app.memory_service = self._originals["memory_service"]
        server_app.runner_router = self._originals["runner_router"]
        server_app.session_waiters = self._originals["session_waiters"]
        server_app.session_tasks = self._originals["session_tasks"]
        server_app.session_subscribers = self._originals["session_subscribers"]
        server_app.subscriber_event_namespaces = self._originals["subscriber_event_namespaces"]
        self._temp_dir.__exit__(None, None, None)

    async def test_harness_runner_generates_result_and_evaluation(self) -> None:
        task = HarnessTaskSpec.from_dict(
            {
                "taskId": "harness-case",
                "nodeId": "node-case",
                "runner": "orchestrator",
                "workspace": ".",
                "task": "Say hello",
                "goal": "Say hello",
                "wsUrl": f"ws://127.0.0.1:{self._port}/ws/orchestrator",
                "queryTrace": True,
                "queryArtifacts": True,
                "expectation": {
                    "requiredEvents": [
                        "orchestrator.session.started",
                        "orchestrator.session.completed",
                        "orchestrator.session.snapshot",
                        "orchestrator.session.history"
                    ],
                    "terminalStatus": "COMPLETED",
                    "requireMessageStream": True,
                    "minHistoryItems": 1,
                    "minTraceItems": 1,
                    "requiredSnapshotFields": ["status", "phase"],
                    "requiredHistoryKinds": ["substep"],
                    "requiredArtifactEvents": []
                }
            }
        )
        output_dir = self._root / "run-output"
        result, evaluation = await run_task(task, output_dir=output_dir)
        self.assertEqual(result.snapshot["status"], "COMPLETED")
        self.assertTrue(evaluation["ok"])
        self.assertTrue(result.trace)
        self.assertIn("items", result.artifacts)
        self.assertTrue((output_dir / "result.json").exists())
        self.assertTrue((output_dir / "evaluation.json").exists())
        saved_result = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(saved_result["terminal_event"]["event"], "orchestrator.session.completed")

    async def test_harness_runner_can_execute_task_directory_and_write_summary(self) -> None:
        task_dir = self._root / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_payload = {
            "taskId": "batch-case-a",
            "nodeId": "node-a",
            "runner": "orchestrator",
            "workspace": ".",
            "task": "Say hello",
            "goal": "Say hello",
            "wsUrl": f"ws://127.0.0.1:{self._port}/ws/orchestrator",
            "expectation": {
                "requiredEvents": [
                    "orchestrator.session.started",
                    "orchestrator.session.completed"
                ],
                "terminalStatus": "COMPLETED",
                "requireMessageStream": True
            }
        }
        (task_dir / "a.json").write_text(json.dumps(task_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        task_payload["taskId"] = "batch-case-b"
        (task_dir / "b.json").write_text(json.dumps(task_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_dir = self._root / "batch-output"
        summary = await run_task_files(sorted(task_dir.glob("*.json")), output_dir=summary_dir)
        self.assertTrue(summary.ok)
        self.assertEqual(summary.task_count, 2)
        self.assertEqual(summary.passed_count, 2)
        self.assertTrue((summary_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
