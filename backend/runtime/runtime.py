from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from backend.config import load_config
from backend.llm.planner import PlannerRuntime
from backend.memory.service import MemoryService
from backend.observability import get_langsmith_tracer
from backend.runtime.graph import build_runtime_graph
from backend.runtime.state import RuntimeState, create_initial_state
from backend.sessions.state import OrchestratorSessionState
from backend.tools import build_langchain_tools, build_tool_definitions, build_tool_map
from backend.workers.registry import WorkerRegistry
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
except Exception:  # pragma: no cover
    MemorySaver = None
    Command = None

AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]
ProgressCallback = Callable[[str, float | None], Awaitable[None]]
SubstepCallback = Callable[[str, str, str, str | None], Awaitable[None]]
MessageEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class RuntimePaused(Exception):
    def __init__(self, state: RuntimeState, *, prompt: str = "", input_mode: str = "text") -> None:
        super().__init__(prompt or "Runtime paused for user input.")
        self.state = state
        self.prompt = prompt
        self.input_mode = input_mode


class OrchestratorRuntime:
    _CHECKPOINTER = MemorySaver() if MemorySaver is not None else None

    def __init__(
        self,
        *,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
        emit_substep: SubstepCallback | None = None,
        emit_message_event: MessageEventCallback | None = None,
    ) -> None:
        self.session = session
        self.emit_progress = emit_progress
        self.await_user = await_user
        self.emit_substep = emit_substep
        self.emit_message_event = emit_message_event
        self.config = load_config()
        self.graph_build = build_runtime_graph(checkpointer=self._CHECKPOINTER)
        self.planner = PlannerRuntime(self.config)
        self.worker_registry = WorkerRegistry(self.config)
        self.memory_service = MemoryService()
        self.tracer = get_langsmith_tracer()
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
        run_id = self.tracer.start_run(
            name="runtime.session",
            run_type="chain",
            inputs={
                "sessionId": self.session.session_id,
                "taskId": self.session.task_id,
                "workspace": self.session.workspace,
                "task": self.session.task,
                "goal": self.session.goal,
            },
            metadata={"module": "runtime", "runner": self.session.runner},
            tags=["runtime", "session"],
        )

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
            "emit_message_event": self.emit_message_event,
            "memory_service": self.memory_service,
            "memory_config": self.config.memory,
            "tracer": self.tracer,
            "langsmith_parent_run_id": run_id,
        }
        recursion_limit = max(50, int(self.config.max_iterations) * 6)
        try:
            runtime_input: RuntimeState | Any = state
            resume_payload = self.session.context.pop("_resume_payload", None)
            if resume_payload is not None and Command is not None:
                runtime_input = Command(
                    resume=resume_payload,
                    update={
                        "context": state["context"],
                        "followups": list(self.session.followups),
                        "worker_sessions": dict(self.session.worker_sessions),
                        "stop_reason": str(self.session.stop_reason or ""),
                    },
                )
            final_state = await self._run_graph_stream(
                input_value=runtime_input,
                state=state,
                recursion_limit=recursion_limit,
            )
            self._apply_runtime_state(final_state)
            self.tracer.end_run(
                run_id,
                outputs={
                    "sessionId": self.session.session_id,
                    "phase": str(final_state.get("phase") or ""),
                    "status": str(final_state.get("status") or ""),
                    "stopReason": str(final_state.get("stop_reason") or ""),
                    "iteration": int(final_state.get("iteration") or 0),
                },
                metadata={"module": "runtime", "runner": self.session.runner},
            )
            return self.session.result
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"sessionId": self.session.session_id},
                error=(str(exc).strip() or "runtime graph failed")[:1200],
                metadata={"module": "runtime", "runner": self.session.runner},
                tags=["error"],
            )
            raise

    async def _run_graph_stream(self, *, input_value: Any, state: RuntimeState, recursion_limit: int) -> RuntimeState:
        graph = self.graph_build.graph
        config = {
            "recursion_limit": recursion_limit,
            "configurable": {"thread_id": self.session.session_id},
        }
        latest_state = RuntimeState(**dict(state))

        if hasattr(graph, "astream"):
            astream_kwargs: dict[str, Any] = {"stream_mode": ["custom", "values"]}
            if self._supports_kwarg(graph.astream, "version"):
                astream_kwargs["version"] = "v2"
            async for mode, payload in graph.astream(input_value, config=config, **astream_kwargs):
                if mode == "values" and isinstance(payload, dict):
                    latest_state = RuntimeState(**{**dict(latest_state), **payload})
                    continue
                if mode == "custom" and isinstance(payload, dict):
                    await self._handle_custom_stream_event(payload)
            return self._resolve_graph_completion(graph=graph, config=config, state=latest_state)

        ainvoke_kwargs: dict[str, Any] = {}
        if self._supports_kwarg(graph.ainvoke, "version"):
            ainvoke_kwargs["version"] = "v2"
        result = await graph.ainvoke(input_value, config=config, **ainvoke_kwargs)
        latest_state = RuntimeState(**{**dict(state), **dict(result or {})})
        return self._resolve_graph_completion(graph=graph, config=config, state=latest_state)

    def _resolve_graph_completion(self, *, graph: Any, config: dict[str, Any], state: RuntimeState) -> RuntimeState:
        get_state = getattr(graph, "get_state", None)
        if not callable(get_state):
            return state
        graph_state = get_state(config)
        values = getattr(graph_state, "values", None)
        if isinstance(values, dict):
            state = RuntimeState(**{**dict(state), **values})
        for task in list(getattr(graph_state, "tasks", ()) or ()):
            interrupts = list(getattr(task, "interrupts", ()) or ())
            if not interrupts:
                continue
            prompt = ""
            input_mode = "text"
            value = getattr(interrupts[0], "value", None)
            if isinstance(value, dict):
                prompt = str(value.get("prompt") or "")
                input_mode = str(value.get("input_mode") or "text")
            state["awaiting_input"] = True
            state["pending_user_prompt"] = prompt
            state["phase"] = "awaiting_user"
            state["status"] = "RUNNING"
            raise RuntimePaused(state, prompt=prompt, input_mode=input_mode)
        return state

    async def _handle_custom_stream_event(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "progress":
            await self.emit_progress(
                str(payload.get("message") or ""),
                float(payload["progress"]) if payload.get("progress") is not None else None,
            )
            return
        if kind == "substep" and self.emit_substep is not None:
            await self.emit_substep(
                str(payload.get("substep_kind") or "runtime"),
                str(payload.get("title") or ""),
                str(payload.get("status") or "running"),
                str(payload.get("detail") or ""),
            )

    @staticmethod
    def _supports_kwarg(fn: Any, name: str) -> bool:
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            return False
        if name in signature.parameters:
            return True
        return any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())

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


