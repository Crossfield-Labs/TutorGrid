from __future__ import annotations

import json
import unittest

from orchestrator.tools.delegate import delegate_task
from orchestrator.workers.models import WorkerResult


class _FakeWorker:
    def __init__(self, name: str, *, succeed: bool = True) -> None:
        self.name = name
        self.succeed = succeed
        self.calls: list[dict[str, object]] = []

    async def run(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.succeed:
            return WorkerResult(worker=self.name, success=True, summary=f"{self.name} ok", output=f"{self.name} output")
        return WorkerResult(worker=self.name, success=False, summary=f"{self.name} failed", output="", error=f"{self.name} error")


class _FakeRegistry:
    def __init__(self, workers: dict[str, _FakeWorker]) -> None:
        self._workers = workers

    def get(self, name: str):
        return self._workers[name]

    def list_names(self) -> list[str]:
        return list(self._workers.keys())


class _FakeSession:
    def __init__(self) -> None:
        self.active_worker = ""
        self.active_session_mode = ""
        self.active_worker_profile = ""
        self.active_worker_task_id = ""
        self.active_worker_can_interrupt = False
        self.worker_runs = []
        self.worker_sessions = {}
        self.artifacts = []
        self.context = {}
        self.phase = "planning"
        self.latest_summary = ""
        self.latest_artifact_summary = ""
        self.permission_summary = ""
        self.session_info_summary = ""
        self.mcp_status_summary = ""
        self.hook_events = []

    def set_active_worker_runtime(self, *, worker: str, session_mode: str, task_id: str, profile: str, can_interrupt: bool = False) -> None:
        self.active_worker = worker
        self.active_session_mode = session_mode
        self.active_worker_task_id = task_id
        self.active_worker_profile = profile
        self.active_worker_can_interrupt = can_interrupt

    def set_latest_summary(self, summary: str) -> None:
        self.latest_summary = summary

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def set_latest_artifact_summary(self, summary: str) -> None:
        self.latest_artifact_summary = summary

    def set_permission_summary(self, summary: str) -> None:
        self.permission_summary = summary

    def set_session_info_summary(self, summary: str) -> None:
        self.session_info_summary = summary

    def set_mcp_status_summary(self, summary: str) -> None:
        self.mcp_status_summary = summary

    def add_hook_event(self, **event) -> None:
        self.hook_events.append(event)


class DelegateRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_delegate_uses_worker_selection_and_fallback(self) -> None:
        registry = _FakeRegistry(
            {
                "opencode": _FakeWorker("opencode", succeed=False),
                "codex": _FakeWorker("codex", succeed=True),
            }
        )
        session = _FakeSession()

        result_json = await delegate_task(
            task="Please implement this fix",
            worker="",
            session_mode="",
            session_key="",
            profile="",
            workspace="D:/works/pc_orchestrator_core",
            worker_registry=registry,
            session=session,
        )

        result = json.loads(result_json)
        self.assertEqual(result["worker"], "codex")
        self.assertTrue(result["success"])
        self.assertEqual(len(registry.get("opencode").calls), 1)
        self.assertEqual(len(registry.get("codex").calls), 1)
        self.assertGreaterEqual(len(session.worker_runs), 2)

