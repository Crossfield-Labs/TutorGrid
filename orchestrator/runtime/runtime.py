from __future__ import annotations

from typing import Awaitable, Callable

from orchestrator.config import load_config
from orchestrator.llm.planner import PlannerRuntime
from orchestrator.runtime.graph import build_runtime_graph
from orchestrator.runtime.state import RuntimeState, create_initial_state
from orchestrator.sessions.state import OrchestratorSessionState
from orchestrator.tools.registry import build_langchain_tools

AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]
ProgressCallback = Callable[[str, float | None], Awaitable[None]]


class OrchestratorRuntime:
    def __init__(
        self,
        *,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> None:
        self.session = session
        self.emit_progress = emit_progress
        self.await_user = await_user
        self.config = load_config()
        self.graph_build = build_runtime_graph()
        self.planner = PlannerRuntime(self.config)
        self.tools = build_langchain_tools(
            workspace=session.workspace,
            shell_timeout_seconds=self.config.shell_timeout_seconds,
            await_user_fn=await_user,
        )

    async def run(self) -> str:
        await self.emit_progress("Bootstrapping LangGraph runtime", 0.05)
        if not self.graph_build.available:
            raise RuntimeError("LangGraph is not installed in the orchestrator environment.")

        state = create_initial_state(
            session_id=self.session.session_id,
            task_id=self.session.task_id,
            node_id=self.session.node_id,
            workspace=self.session.workspace,
            task=self.session.task,
            goal=self.session.goal,
            max_iterations=self.config.max_iterations,
        )
        state["status"] = "RUNNING"
        state["phase"] = "planning"
        state["context"] = {
            "planner": self.planner,
            "tools": self.tools,
            "session": self.session,
        }
        result = await self.graph_build.graph.ainvoke(state)
        final_state = RuntimeState(**{**dict(state), **dict(result)})
        self.session.phase = str(final_state.get("phase") or "completed")
        self.session.status = str(final_state.get("status") or "COMPLETED")
        self.session.latest_summary = str(final_state.get("latest_summary") or "")
        self.session.last_progress_message = str(final_state.get("last_progress_message") or "")
        self.session.result = str(final_state.get("final_answer") or "")
        return self.session.result
