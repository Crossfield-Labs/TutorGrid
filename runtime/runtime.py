from __future__ import annotations

from typing import Awaitable, Callable

from config import load_config
from llm.planner import PlannerRuntime
from runtime.graph import build_runtime_graph
from runtime.state import RuntimeState, create_initial_state
from sessions.state import OrchestratorSessionState
from tools import build_langchain_tools, build_tool_definitions, build_tool_map
from workers.registry import WorkerRegistry

AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]
ProgressCallback = Callable[[str, float | None], Awaitable[None]]
SubstepCallback = Callable[[str, str, str, str | None], Awaitable[None]]


class OrchestratorRuntime:
    def __init__(
        self,
        *,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
        emit_substep: SubstepCallback | None = None,
    ) -> None:
        self.session = session
        self.emit_progress = emit_progress
        self.await_user = await_user
        self.emit_substep = emit_substep
        self.config = load_config()
        self.graph_build = build_runtime_graph()
        self.planner = PlannerRuntime(self.config)
        self.worker_registry = WorkerRegistry(self.config)
        self.tools = build_langchain_tools(
            workspace=session.workspace,
            shell_timeout_seconds=self.config.shell_timeout_seconds,
            await_user_fn=await_user,
            worker_registry=self.worker_registry,
            session=session,
        )
        self.tool_map = build_tool_map(self.tools)
        self.tool_definitions = build_tool_definitions(self.tools)

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
        state["followups"] = list(self.session.followups)
        state["worker_sessions"] = dict(self.session.worker_sessions)
        state["stop_reason"] = str(self.session.stop_reason or "")
        state["messages"] = list(self.session.context.get("planner_messages") or [])
        state["context"] = {
            "planner": self.planner,
            "tools": self.tools,
            "tool_map": self.tool_map,
            "tool_definitions": self.tool_definitions,
            "session": self.session,
            "emit_progress": self.emit_progress,
            "emit_substep": self.emit_substep,
        }
        recursion_limit = max(50, int(self.config.max_iterations) * 6)
        result = await self.graph_build.graph.ainvoke(state, config={"recursion_limit": recursion_limit})
        final_state = RuntimeState(**{**dict(state), **dict(result)})
        self._apply_runtime_state(final_state)
        return self.session.result

    def _apply_runtime_state(self, final_state: RuntimeState) -> None:
        self.session.phase = str(final_state.get("phase") or self.session.phase or "completed")
        self.session.status = str(final_state.get("status") or self.session.status or "COMPLETED")
        self.session.latest_summary = str(final_state.get("latest_summary") or self.session.latest_summary or "")
        self.session.last_progress_message = str(
            final_state.get("last_progress_message") or self.session.last_progress_message or ""
        )
        self.session.latest_artifact_summary = str(
            final_state.get("latest_artifact_summary") or self.session.latest_artifact_summary or ""
        )
        self.session.active_worker = str(final_state.get("active_worker") or self.session.active_worker or "")
        self.session.active_session_mode = str(
            final_state.get("active_session_mode") or self.session.active_session_mode or ""
        )
        self.session.active_worker_profile = str(
            final_state.get("active_worker_profile") or self.session.active_worker_profile or ""
        )
        self.session.active_worker_task_id = str(
            final_state.get("active_worker_task_id") or self.session.active_worker_task_id or ""
        )
        self.session.active_worker_can_interrupt = bool(
            final_state.get("active_worker_can_interrupt")
            if "active_worker_can_interrupt" in final_state
            else self.session.active_worker_can_interrupt
        )
        self.session.awaiting_input = bool(final_state.get("awaiting_input") or False)
        self.session.pending_user_prompt = str(final_state.get("pending_user_prompt") or "")
        self.session.stop_reason = str(final_state.get("stop_reason") or self.session.stop_reason or "")
        self.session.followups = list(final_state.get("followups") or self.session.followups)
        self.session.artifacts = list(final_state.get("artifacts") or self.session.artifacts)
        self.session.worker_runs = list(final_state.get("worker_runs") or self.session.worker_runs)
        self.session.worker_sessions = dict(final_state.get("worker_sessions") or self.session.worker_sessions)
        self.session.substeps = list(final_state.get("substeps") or self.session.substeps)
        self.session.context["planner_messages"] = list(final_state.get("messages") or [])
        self.session.context["tool_events"] = list(final_state.get("tool_events") or [])
        self.session.result = str(final_state.get("final_answer") or self.session.result or "")

