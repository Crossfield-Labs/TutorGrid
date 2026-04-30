from __future__ import annotations

import asyncio
import json
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from backend.memory.service import MemoryService
from backend.runners.base import AwaitUserCallback, BaseRunner, MessageEventCallback, ProgressCallback, SubstepCallback
from backend.server import app as server_app
from backend.sessions.manager import SessionManager
from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore
from backend.storage.sqlite_store import SQLiteSessionStore
from tests.temp_paths import workspace_temp_dir
from websockets.legacy.client import connect
from websockets.legacy.server import serve


class _FakeWorkerControl:
    def __init__(self) -> None:
        self.worker = "fake-worker"
        self.can_interrupt = True
        self._event = asyncio.Event()

    async def interrupt(self) -> dict[str, object]:
        self._event.set()
        return {"accepted": True, "worker": self.worker}

    async def wait(self) -> None:
        await self._event.wait()


class _ScenarioRunner(BaseRunner):
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
        task_text = session.task.lower()

        if self._emit_substep is not None:
            await self._emit_substep("tool", "Prepare", "started", f"prepare:{session.task}")

        if "fail" in task_text:
            await emit_progress("Preparing to fail", 0.2)
            raise RuntimeError("simulated failure")

        if "wait" in task_text:
            await emit_progress("Waiting for user input", 0.25)
            reply = await await_user("Please provide extra input", "text")
            if self._emit_substep is not None:
                await self._emit_substep("tool", "Reply consumed", "completed", reply)
            await emit_progress(f"Reply consumed: {reply}", 0.8)
            return f"reply={reply}"

        if "interrupt" in task_text:
            control = _FakeWorkerControl()
            session.context["_active_worker_control"] = control
            session.set_active_worker_runtime(
                worker="fake-worker",
                session_mode="resume",
                task_id="fake-task",
                profile="test",
                can_interrupt=True,
            )
            await emit_progress("Interruptible runner is active", 0.4)
            await control.wait()
            await asyncio.sleep(0.05)
            if self._emit_substep is not None:
                await self._emit_substep("worker", "Interrupt acknowledged", "completed", "interrupt handled")
            await emit_progress("Interrupt handled", 0.95)
            return "interrupted"

        await emit_progress("Running happy-path task", 0.3)
        if self._emit_substep is not None:
            await self._emit_substep("tool", "Prepare", "completed", "done")
        if self._emit_message_event is not None:
            payload = {
                "messageId": f"{session.session_id}:assistant:1:1",
                "role": "assistant",
                "contentType": "text/markdown",
                "phase": "planning",
            }
            await self._emit_message_event("started", payload)
            await self._emit_message_event("delta", {**payload, "delta": "fake "})
            await self._emit_message_event("delta", {**payload, "delta": "result"})
            await self._emit_message_event("completed", {**payload, "content": "fake result", "finishReason": "stop"})
        session.set_latest_summary("fake summary generated")
        return "fake result"


class _FakeRouter:
    def __init__(self) -> None:
        self._runner = _ScenarioRunner()

    def get(self, runner_name: str) -> BaseRunner:
        return self._runner


class WebSocketE2ETests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._temp_dir = workspace_temp_dir("ws-e2e-")
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
        server_app.runner_router = _FakeRouter()
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
        self._websocket = await connect(f"ws://127.0.0.1:{self._port}/ws/orchestrator")
        self._buffer: list[dict[str, Any]] = []

    async def asyncTearDown(self) -> None:
        await self._websocket.close()
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

    async def test_start_snapshot_history_trace_memory_search(self) -> None:
        await self._send_request(
            "orchestrator.session.start",
            task_id="task-start",
            node_id="node-start",
            params={"runner": "orchestrator", "workspace": ".", "task": "Explain arrays"},
        )
        started = await self._recv_event("orchestrator.session.started")
        session_id = str(started["sessionId"])
        completed = await self._recv_event("orchestrator.session.completed", session_id=session_id)
        self.assertEqual(completed["payload"]["result"], "fake result")
        started_message = await self._recv_event("orchestrator.session.message.started", session_id=session_id)
        self.assertEqual(started_message["payload"]["role"], "assistant")
        delta_events = [
            await self._recv_event("orchestrator.session.message.delta", session_id=session_id),
            await self._recv_event("orchestrator.session.message.delta", session_id=session_id),
        ]
        self.assertEqual("".join(event["payload"]["delta"] for event in delta_events), "fake result")
        completed_message = await self._recv_event("orchestrator.session.message.completed", session_id=session_id)
        self.assertEqual(completed_message["payload"]["content"], "fake result")

        await self._send_request(
            "orchestrator.session.snapshot",
            session_id=session_id,
            params={},
        )
        snapshot_event = await self._recv_event(
            "orchestrator.session.snapshot",
            session_id=session_id,
            predicate=lambda event: event["payload"]["snapshot"]["status"] == "COMPLETED",
        )
        self.assertEqual(snapshot_event["payload"]["snapshot"]["status"], "COMPLETED")

        await self._send_request(
            "orchestrator.session.history",
            session_id=session_id,
            params={"limit": 50},
        )
        history_event = await self._recv_event("orchestrator.session.history", session_id=session_id)
        self.assertTrue(history_event["payload"]["items"])

        trace_items = server_app.trace_store.list_session_history(session_id, limit=50)
        self.assertTrue(trace_items)
        self.assertTrue(any(item["event"].endswith(".completed") for item in trace_items))

        await self._send_request(
            "orchestrator.memory.compact",
            session_id=session_id,
            params={"limit": 50},
        )
        compact_event = await self._recv_event("orchestrator.memory.compact", session_id=session_id)
        self.assertGreater(compact_event["payload"]["documentCount"], 0)

        await self._send_request(
            "orchestrator.memory.search",
            session_id=session_id,
            params={"text": "Explain arrays", "limit": 5},
        )
        search_event = await self._recv_event("orchestrator.memory.search", session_id=session_id)
        self.assertTrue(search_event["payload"]["items"])

    async def test_tiptap_execute_sends_command_response_before_session_started(self) -> None:
        await self._send_request(
            "orchestrator.tiptap.command",
            task_id="tiptap-order",
            node_id="node-tiptap",
            params={
                "runner": "orchestrator",
                "workspace": ".",
                "commandName": "explain-selection",
                "selectionText": "observer pattern",
                "execute": True,
            },
        )

        command_event = await self._recv_any()
        self.assertEqual(command_event["event"], "orchestrator.tiptap.command")
        session_id = str(command_event["sessionId"])
        self.assertEqual(command_event["payload"]["mode"], "start")
        self.assertEqual(command_event["payload"]["sessionId"], session_id)

        started_event = await self._recv_any()
        self.assertEqual(started_event["event"], "orchestrator.session.started")
        self.assertEqual(started_event["sessionId"], session_id)

    async def test_tiptap_execute_start_emits_stream_message_events_and_completion(self) -> None:
        await self._send_request(
            "orchestrator.tiptap.command",
            task_id="tiptap-stream",
            node_id="node-tiptap",
            params={
                "runner": "orchestrator",
                "workspace": ".",
                "commandName": "summarize-selection",
                "selectionText": "arrays store ordered values",
                "execute": True,
            },
        )

        command_event = await self._recv_event("orchestrator.tiptap.command")
        session_id = str(command_event["sessionId"])
        await self._recv_event("orchestrator.session.started", session_id=session_id)
        await self._recv_event("orchestrator.session.phase", session_id=session_id)
        started_message = await self._recv_event("orchestrator.session.message.started", session_id=session_id)
        self.assertTrue(started_message["payload"]["messageId"])
        delta = await self._recv_event("orchestrator.session.message.delta", session_id=session_id)
        self.assertEqual(delta["payload"]["messageId"], started_message["payload"]["messageId"])
        self.assertTrue(delta["payload"]["delta"])
        completed_message = await self._recv_event("orchestrator.session.message.completed", session_id=session_id)
        self.assertEqual(completed_message["payload"]["messageId"], started_message["payload"]["messageId"])
        completed = await self._recv_event("orchestrator.session.completed", session_id=session_id)
        self.assertEqual(completed["payload"]["result"], "fake result")

    async def test_tiptap_execute_with_running_session_queues_followup(self) -> None:
        await self._send_request(
            "orchestrator.session.start",
            task_id="tiptap-running-followup",
            node_id="node-running",
            params={"runner": "orchestrator", "workspace": ".", "task": "wait for reply"},
        )
        await_user_event = await self._recv_event("orchestrator.session.await_user")
        session_id = str(await_user_event["sessionId"])

        await self._send_request(
            "orchestrator.tiptap.command",
            session_id=session_id,
            params={
                "runner": "orchestrator",
                "workspace": ".",
                "commandName": "explain-selection",
                "selectionText": "binary search",
                "execute": True,
            },
        )

        command_event = await self._recv_event("orchestrator.tiptap.command", session_id=session_id)
        self.assertEqual(command_event["payload"]["mode"], "followup")
        self.assertEqual(command_event["payload"]["sessionId"], session_id)
        session = server_app.session_manager.get(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(len(session.followups), 1)

    async def test_tiptap_execute_with_completed_session_starts_new_session(self) -> None:
        await self._send_request(
            "orchestrator.session.start",
            task_id="tiptap-completed-base",
            node_id="node-completed",
            params={"runner": "orchestrator", "workspace": ".", "task": "finish normally"},
        )
        completed = await self._recv_event("orchestrator.session.completed")
        old_session_id = str(completed["sessionId"])

        await self._send_request(
            "orchestrator.tiptap.command",
            session_id=old_session_id,
            params={
                "runner": "orchestrator",
                "workspace": ".",
                "commandName": "generate-flashcards",
                "selectionText": "stacks are last-in first-out",
                "execute": True,
            },
        )

        command_event = await self._recv_event("orchestrator.tiptap.command")
        new_session_id = str(command_event["sessionId"])
        self.assertEqual(command_event["payload"]["mode"], "start")
        self.assertEqual(command_event["payload"]["previousSessionId"], old_session_id)
        self.assertNotEqual(new_session_id, old_session_id)
        await self._recv_event("orchestrator.session.started", session_id=new_session_id)
        await self._recv_event("orchestrator.session.completed", session_id=new_session_id)

    async def test_input_interrupt_and_errors(self) -> None:
        await self._send_request(
            "orchestrator.session.start",
            task_id="task-wait",
            node_id="node-wait",
            params={"runner": "orchestrator", "workspace": ".", "task": "wait for reply"},
        )
        await_user_event = await self._recv_event("orchestrator.session.await_user")
        waiting_session_id = str(await_user_event["sessionId"])

        await self._send_request(
            "orchestrator.session.input",
            session_id=waiting_session_id,
            params={"text": "extra context", "inputIntent": "reply"},
        )
        followup_accepted = await self._recv_event(
            "orchestrator.session.followup.accepted",
            session_id=waiting_session_id,
        )
        self.assertEqual(followup_accepted["payload"]["intent"], "reply")
        completed = await self._recv_event("orchestrator.session.completed", session_id=waiting_session_id)
        self.assertEqual(completed["payload"]["result"], "reply=extra context")

        await self._send_request(
            "orchestrator.session.start",
            task_id="task-fail",
            node_id="node-fail",
            params={"runner": "orchestrator", "workspace": ".", "task": "please fail"},
        )
        failed = await self._recv_event("orchestrator.session.failed")
        failed_session_id = str(failed["sessionId"])
        self.assertIn("simulated failure", failed["payload"]["error"])

        await self._send_request(
            "orchestrator.session.history",
            session_id=failed_session_id,
            params={"limit": 50},
        )
        history_event = await self._recv_event("orchestrator.session.history", session_id=failed_session_id)
        self.assertTrue(any(item["kind"] == "error" for item in history_event["payload"]["items"]))

        interrupt_session = server_app.session_manager.create(
            task_id="task-interrupt",
            node_id="node-interrupt",
            runner="orchestrator",
            workspace=".",
            task="interrupt this task",
            goal="interrupt this task",
        )
        interrupt_session.mark(status="RUNNING", message="Interruptible runner is active")
        interrupt_control = _FakeWorkerControl()
        interrupt_session.context["_active_worker_control"] = interrupt_control
        interrupt_session.set_active_worker_runtime(
            worker="fake-worker",
            session_mode="resume",
            task_id="fake-task",
            profile="test",
            can_interrupt=True,
        )
        server_app.session_manager.update(interrupt_session)
        interrupt_session_id = interrupt_session.session_id

        await self._send_request(
            "orchestrator.session.interrupt",
            session_id=interrupt_session_id,
            params={"text": "stop now"},
        )
        await self._wait_until(
            lambda: interrupt_control._event.is_set()
            or (
                server_app.session_manager.get(interrupt_session_id) is not None
                and server_app.session_manager.get(interrupt_session_id).stop_reason == "interrupt_requested"
            ),
            timeout=8.0,
        )

        await self._send_request(
            "orchestrator.session.snapshot",
            session_id=interrupt_session_id,
            params={},
        )
        snapshot_event = await self._recv_event(
            "orchestrator.session.snapshot",
            session_id=interrupt_session_id,
            predicate=lambda event: event["payload"]["snapshot"].get("stopReason") == "interrupt_requested"
            or event["payload"]["snapshot"].get("status") == "COMPLETED",
        )
        snapshot = snapshot_event["payload"]["snapshot"]
        self.assertTrue(
            snapshot["stopReason"] == "interrupt_requested" or snapshot["status"] == "COMPLETED"
        )
        self.assertTrue(interrupt_control._event.is_set())

    async def _send_request(
        self,
        method: str,
        *,
        task_id: str | None = None,
        node_id: str | None = None,
        session_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "type": "req",
            "id": f"{method}-{task_id or session_id or 'request'}",
            "method": method,
            "taskId": task_id,
            "nodeId": node_id,
            "sessionId": session_id,
            "params": params or {},
        }
        await self._websocket.send(json.dumps(payload, ensure_ascii=False))

    async def _recv_event(
        self,
        event_name: str,
        *,
        session_id: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        def matches(item: dict[str, Any]) -> bool:
            if item.get("event") != event_name:
                return False
            if session_id is not None and item.get("sessionId") != session_id:
                return False
            if predicate is not None and not predicate(item):
                return False
            return True

        for index, buffered in enumerate(self._buffer):
            if matches(buffered):
                return self._buffer.pop(index)

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AssertionError(f"Timed out waiting for {event_name}")
            raw = await asyncio.wait_for(self._websocket.recv(), timeout=remaining)
            item = json.loads(raw)
            if matches(item):
                return item
            self._buffer.append(item)

    async def _recv_any(self, *, timeout: float = 20.0) -> dict[str, Any]:
        if self._buffer:
            return self._buffer.pop(0)
        raw = await asyncio.wait_for(self._websocket.recv(), timeout=timeout)
        return json.loads(raw)

    async def _wait_until(self, predicate: Callable[[], bool], *, timeout: float = 5.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Timed out waiting for test condition")
            await asyncio.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
