from __future__ import annotations

import unittest

from backend.providers.base import LLMResponse, ToolCallRequest
from backend.runtime.nodes.planning import _filter_duplicate_tool_calls, planning_node
from backend.runtime.state import create_initial_state
from backend.sessions.state import OrchestratorSessionState


class _PlannerStub:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response

    async def plan(self, *, task: str, goal: str, workspace: str, history, tools):
        return list(history), self.response

    async def finalize_from_evidence(self, *, task: str, goal: str, workspace: str, history, evidence, reason: str) -> str:
        return "根据已有证据可以收口。"

    def build_fallback_summary(self, *, task: str, workspace: str, evidence, reason: str) -> str:
        return f"fallback: {reason}"


class PlanningNodeTests(unittest.IsolatedAsyncioTestCase):
    def test_filter_duplicate_tool_calls_suppresses_previous_and_local_duplicates(self) -> None:
        filtered, dropped = _filter_duplicate_tool_calls(
            [
                {"id": "1", "tool": "list_files", "arguments": {"path": "."}},
                {"id": "2", "tool": "list_files", "arguments": {"path": "."}},
                {"id": "3", "tool": "read_file", "arguments": {"path": "main.py"}},
            ],
            tool_events=[{"tool": "read_file", "arguments": {"path": "main.py"}, "result": "x"}],
        )
        self.assertEqual(dropped, 2)
        self.assertEqual(filtered, [{"id": "1", "tool": "list_files", "arguments": {"path": "."}}])

    async def test_planning_finalizes_when_only_duplicate_calls_remain_and_evidence_exists(self) -> None:
        session = OrchestratorSessionState(
            task_id="t1",
            node_id="n1",
            runner="orchestrator",
            workspace="D:/works/pc_orchestrator_core",
            task="了解项目",
            goal="了解项目",
        )
        state = create_initial_state(
            session_id=session.session_id,
            task_id=session.task_id,
            node_id=session.node_id,
            workspace=session.workspace,
            task=session.task,
            goal=session.goal,
            max_iterations=8,
        )
        state["iteration"] = 4
        state["tool_results"] = [{"tool": "list_files", "result": "files"}]
        state["tool_events"] = [{"tool": "list_files", "arguments": {"path": "."}, "result": "files"}]
        state["context"] = {
            "planner": _PlannerStub(
                LLMResponse(
                    content="",
                    tool_calls=[ToolCallRequest(id="1", name="list_files", arguments={"path": "."})],
                )
            ),
            "tool_definitions": [],
            "session": session,
            "emit_progress": None,
        }

        result = await planning_node(state)
        self.assertEqual(result["stop_reason"], "completed_after_duplicate_suppression")
        self.assertTrue(result["final_answer"])



