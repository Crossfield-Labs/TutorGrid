from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.runtime.nodes.await_user import await_user_node
from backend.runtime.nodes.tools import tools_node
from backend.runtime.state import create_initial_state
from backend.sessions.state import OrchestratorSessionState


class InterruptRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_node_intercepts_await_user_tool_into_runtime_pause(self) -> None:
        session = OrchestratorSessionState(
            task_id="task-await",
            node_id="node-await",
            runner="orchestrator",
            workspace=".",
            task="ask user",
            goal="ask user",
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
        state["planned_tool_calls"] = [
            {
                "id": "tool-1",
                "tool": "await_user",
                "arguments": {"message": "请选择数据源", "input_mode": "text"},
            }
        ]
        state["context"] = {
            "session": session,
            "tool_map": {},
            "emit_progress": None,
        }

        result = await tools_node(state)

        self.assertTrue(result["awaiting_input"])
        self.assertEqual(result["phase"], "awaiting_user")
        self.assertEqual(result["pending_user_prompt"], "请选择数据源")
        self.assertEqual(result["planned_tool_calls"], [])
        self.assertEqual(session.pending_user_prompt, "请选择数据源")
        self.assertEqual(session.context["pending_user_input_mode"], "text")
        self.assertEqual(result["tool_events"][-1]["tool"], "await_user")

    async def test_await_user_node_resumes_via_interrupt_payload(self) -> None:
        session = OrchestratorSessionState(
            task_id="task-resume",
            node_id="node-resume",
            runner="orchestrator",
            workspace=".",
            task="resume task",
            goal="resume task",
        )
        session.request_user_input("请补充输入", "text")
        session.context["pending_user_input_mode"] = "text"
        state = create_initial_state(
            session_id=session.session_id,
            task_id=session.task_id,
            node_id=session.node_id,
            workspace=session.workspace,
            task=session.task,
            goal=session.goal,
            max_iterations=8,
        )
        state["awaiting_input"] = True
        state["pending_user_prompt"] = "请补充输入"
        state["phase"] = "awaiting_user"
        state["messages"] = []
        state["tool_events"] = []
        state["context"] = {
            "session": session,
            "emit_progress": None,
        }

        with patch("backend.runtime.nodes.await_user.interrupt", return_value={"content": "resume payload"}):
            result = await await_user_node(state)

        self.assertFalse(result["awaiting_input"])
        self.assertEqual(result["phase"], "planning")
        self.assertEqual(result["pending_user_prompt"], "")
        self.assertIn("resume payload", result["messages"][-1]["content"])
        self.assertEqual(result["tool_events"][-1]["result"], "resume payload")
        self.assertFalse(session.awaiting_input)
        self.assertEqual(session.context["last_user_input"], "resume payload")


if __name__ == "__main__":
    unittest.main()
