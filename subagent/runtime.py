from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from config.subagent_config import SubAgentConfig, load_subagent_config
from providers.registry import ProviderRegistry
from sessions.session_state import PcSessionState
from subagent.capabilities import (
    AwaitUserTool,
    DelegateOpenCodeTool,
    ListFilesTool,
    ReadFileTool,
    RunShellTool,
    WebFetchTool,
)
from subagent.capabilities.agent_delegate import DelegateAgentTool
from subagent.context_builder import ContextBuilder
from subagent.models import RuntimeState, SubstepRecord
from subagent.tool_registry import ToolRegistry
from workers.models import WorkerControlRef, WorkerProgressEvent, WorkerResult
from workers.registry import WorkerRegistry

ProgressCallback = Callable[[str, float | None], Awaitable[None]]
AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]
SubstepCallback = Callable[[str, str, str, str | None], Awaitable[None]]


class PcSubAgentRuntime:
    def __init__(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
        emit_substep: SubstepCallback | None = None,
        config: SubAgentConfig | None = None,
    ) -> None:
        self.session = session
        self.emit_progress = emit_progress
        self.await_user = await_user
        self.emit_substep = emit_substep
        self.config = config or load_subagent_config()
        planner = self.config.planner
        try:
            self.provider = ProviderRegistry.create(
                provider_type=planner.provider,
                api_key=planner.api_key,
                api_base=planner.api_base,
                model=planner.model,
                temperature=planner.temperature,
                max_tokens=planner.max_tokens,
            )
        except Exception as error:
            raise RuntimeError(
                "PC sub-agent planner configuration is invalid. "
                "Please set METAAGENT_SUBAGENT_PROVIDER/MODEL/API_BASE/API_KEY "
                "or fill pc_orchestrator/config/subagent_config.json first."
            ) from error

        self.tools = ToolRegistry()
        self.workers = WorkerRegistry(self.config)
        worker_sessions = self.session.worker_sessions or {}
        if not worker_sessions:
            context_sessions = self.session.context.get("worker_sessions")
            if isinstance(context_sessions, dict):
                worker_sessions = dict(context_sessions)
        self.session.worker_sessions = worker_sessions
        self.state = RuntimeState(
            workspace=session.workspace or ".",
            goal=session.task or session.goal,
            session_id=session.session_id,
            phase=session.phase or "planning",
            active_worker=session.active_worker or "",
            active_session_mode=session.active_session_mode or "",
            latest_summary=session.latest_summary or "",
            stop_reason=session.stop_reason or "",
            worker_sessions=worker_sessions,
        )
        self.session.context["worker_sessions"] = self.state.worker_sessions
        self._register_tools()

    async def run(self) -> str:
        messages = ContextBuilder.build_messages(self.session)
        self._set_phase("planning")
        for iteration in range(self.config.max_iterations):
            await self._consume_pending_followups(messages)
            self._set_phase("planning")
            await self.emit_progress(
                f"PC sub-agent planning iteration {iteration + 1}",
                min(0.08 + iteration * 0.06, 0.6),
            )
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
            )

            if response.has_tool_calls:
                assistant_tool_calls = [
                    {
                        "id": item.id,
                        "type": "function",
                        "function": {
                            "name": item.name,
                            "arguments": json.dumps(item.arguments, ensure_ascii=False),
                        },
                    }
                    for item in response.tool_calls
                ]
                ContextBuilder.append_assistant_message(
                    messages,
                    content=response.content,
                    tool_calls=assistant_tool_calls,
                )

                for tool_call in response.tool_calls:
                    self._apply_phase_for_tool(tool_call.name)
                    await self._emit_substep("started", tool_call.name, f"Executing {tool_call.name}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    self.state.tool_events.append(
                        {
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments,
                            "result": result,
                        }
                    )
                    ContextBuilder.append_tool_result(
                        messages,
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        result=result,
                    )
                    summary = self._summarize_result(result)
                    self._set_latest_summary(summary)
                    await self._emit_substep("completed", tool_call.name, summary)

                self.session.context["planner_messages"] = messages
                if self._should_attempt_forced_finish(iteration):
                    final_answer = await self._try_finalize_from_evidence(
                        messages,
                        reason="Enough evidence has already been collected to conclude the task.",
                    )
                    if final_answer:
                        self._set_phase("completed")
                        self.session.set_stop_reason("completed_from_evidence")
                        return final_answer
                continue

            final_answer = (response.content or "").strip()
            if final_answer:
                self.session.context["planner_messages"] = messages + [{"role": "assistant", "content": final_answer}]
                self.state.final_answer = final_answer
                self._set_latest_summary(final_answer)
                self._set_phase("completed")
                self.session.set_stop_reason("completed")
                return final_answer

        if self._has_completion_evidence():
            final_answer = await self._try_finalize_from_evidence(
                messages,
                reason=(
                    f"The maximum iteration limit ({self.config.max_iterations}) was reached, "
                    "so finalize from the evidence already collected."
                ),
            )
            if final_answer:
                self._set_phase("completed")
                self.session.set_stop_reason("max_iterations_finalized")
                return final_answer

        self._set_phase("failed")
        self.session.set_stop_reason("max_iterations")
        raise RuntimeError(
            f"PC sub-agent reached the maximum iteration limit ({self.config.max_iterations}) without finishing."
        )

    def _register_tools(self) -> None:
        self.tools.register(ListFilesTool(self.session.workspace))
        self.tools.register(ReadFileTool(self.session.workspace))
        self.tools.register(RunShellTool(self.session.workspace, timeout_seconds=self.config.shell_timeout_seconds))
        self.tools.register(WebFetchTool())
        self.tools.register(
            DelegateAgentTool(
                workspace=self.session.workspace,
                workers=self.workers,
                worker_sessions=self.state.worker_sessions,
                on_progress=self._on_worker_progress,
                on_result=self._on_worker_result,
                on_control=self._on_worker_control,
            )
        )
        self.tools.register(
            DelegateOpenCodeTool(
                workspace=self.session.workspace,
                worker=self.workers.get("opencode"),
                on_progress=self._on_worker_progress,
                on_result=self._on_worker_result,
            )
        )
        self.tools.register(AwaitUserTool(self.await_user))

    async def _consume_pending_followups(self, messages: list[dict[str, Any]]) -> None:
        followups = self.session.drain_followups()
        if not followups:
            return

        for followup in followups:
            intent = str(followup.get("intent") or "chat").strip().lower() or "chat"
            text = str(followup.get("text") or "").strip()
            target = str(followup.get("target") or "").strip()
            if not text:
                continue

            if intent == "redirect":
                self._set_phase("planning")
                self._set_latest_summary(f"Accepted a direction change: {text}")
                content = (
                    "The user changed direction for the current PC task.\n"
                    "Treat this as a high-priority update and revise the plan without forgetting the existing state.\n"
                    f"Direction change: {text}"
                )
            else:
                self._set_latest_summary(f"Accepted a follow-up message: {text}")
                content = (
                    "The user sent a follow-up message for the current PC task.\n"
                    "Use it as additional context while continuing the same task.\n"
                    f"Follow-up: {text}"
                )

            if target:
                content += f"\nTarget: {target}"

            messages.append({"role": "user", "content": content})
            await self._emit_substep(
                "completed",
                "followup",
                f"Accepted {intent} follow-up: {text[:140]}",
            )

        self.session.context["planner_messages"] = messages

    async def _emit_substep(self, status: str, title: str, detail: str) -> None:
        self.state.substeps.append(SubstepRecord(kind="tool", title=title, detail=detail, status=status))
        self.session.context["substeps"] = [
            {
                "kind": item.kind,
                "title": item.title,
                "detail": item.detail,
                "status": item.status,
                "metadata": item.metadata,
            }
            for item in self.state.substeps
        ]
        if self.emit_substep:
            await self.emit_substep("tool", title, status, detail)

    async def _on_worker_progress(self, event: WorkerProgressEvent) -> None:
        metadata = event.metadata or {}
        selected_worker = str(metadata.get("selected_worker") or metadata.get("worker") or "").strip()
        session_mode = str(metadata.get("session_mode") or "").strip()
        worker_profile = str(metadata.get("worker_profile") or "").strip()
        task_id = str(metadata.get("task_id") or "").strip()
        if selected_worker:
            self._set_active_worker(
                selected_worker,
                session_mode or self.state.active_session_mode,
                task_id=task_id,
                profile=worker_profile,
            )
        elif session_mode and self.state.active_worker:
            self._set_active_worker(
                self.state.active_worker,
                session_mode,
                task_id=task_id or self.session.active_worker_task_id,
                profile=worker_profile or self.session.active_worker_profile,
            )
        elif worker_profile and self.state.active_worker:
            self._set_active_worker(
                self.state.active_worker,
                self.state.active_session_mode,
                task_id=task_id or self.session.active_worker_task_id,
                profile=worker_profile,
            )
        elif task_id and self.state.active_worker:
            self._set_active_worker(
                self.state.active_worker,
                self.state.active_session_mode,
                task_id=task_id,
                profile=self.session.active_worker_profile,
            )

        if event.phase == "worker_reroute":
            self._set_phase("delegating")
        elif event.phase.startswith("worker_"):
            self._set_phase("delegating")

        hook_event = str(metadata.get("hook_event") or "").strip()
        if hook_event:
            self.session.add_hook_event(
                name=hook_event,
                message=event.message,
                tool_name=str(metadata.get("tool_name") or "").strip(),
                status=str(metadata.get("hook_status") or "").strip(),
            )

        permission_summary = str(metadata.get("permission_summary") or "").strip()
        if permission_summary:
            self.session.set_permission_summary(permission_summary)

        session_info_summary = str(metadata.get("session_info_summary") or "").strip()
        if session_info_summary:
            self.session.set_session_info_summary(session_info_summary)

        mcp_status_summary = str(metadata.get("mcp_status_summary") or "").strip()
        if mcp_status_summary:
            self.session.set_mcp_status_summary(mcp_status_summary)

        self._set_latest_summary(event.message)
        await self.emit_progress(event.message, 0.72)
        if self.emit_substep:
            await self.emit_substep("worker", event.phase or "worker", "progress", event.message)

    async def _on_worker_result(self, result: WorkerResult) -> None:
        record = result.to_record()
        self.state.worker_runs.append(record)
        self.session.worker_runs.append(record)
        self.session.context["worker_runs"] = self.state.worker_runs
        self.session.context["worker_sessions"] = self.state.worker_sessions
        self._set_active_worker(
            result.worker,
            result.session.mode if result.session is not None else self.state.active_session_mode,
            profile=str(result.metadata.get("worker_profile") or self.session.active_worker_profile),
        )
        if result.metadata:
            permission_summary = str(result.metadata.get("permission_summary") or "").strip()
            if permission_summary:
                self.session.set_permission_summary(permission_summary)
            session_info_summary = str(result.metadata.get("session_info_summary") or "").strip()
            if session_info_summary:
                self.session.set_session_info_summary(session_info_summary)
            mcp_status_summary = str(result.metadata.get("mcp_status_summary") or "").strip()
            if mcp_status_summary:
                self.session.set_mcp_status_summary(mcp_status_summary)
        self.session.context.pop("_active_worker_control", None)
        self.session.set_active_worker_runtime(
            worker=self.session.active_worker,
            session_mode=self.session.active_session_mode,
            task_id=self.session.active_worker_task_id,
            profile=self.session.active_worker_profile,
            can_interrupt=False,
        )

        artifact_paths = [artifact.path for artifact in result.artifacts]
        if artifact_paths:
            self.state.artifacts.extend(artifact_paths)
            self.session.artifacts = sorted(set([*self.session.artifacts, *artifact_paths]))
            artifact_summary = f"{len(artifact_paths)} artifact(s): " + ", ".join(artifact_paths[:3])
            remaining = len(artifact_paths) - 3
            if remaining > 0:
                artifact_summary += f", and {remaining} more"
            self.session.set_latest_artifact_summary(artifact_summary)

        detail = result.summary or result.output[:200] or f"{result.worker} finished"
        self._set_latest_summary(detail)
        self._set_phase("verifying" if result.success else "planning")

        if self.emit_substep:
            await self.emit_substep("worker", result.worker, "completed" if result.success else "failed", detail)

    def _apply_phase_for_tool(self, tool_name: str) -> None:
        if tool_name in {"delegate_agent", "delegate_opencode"}:
            self._set_phase("delegating")
            return
        if tool_name == "await_user":
            self._set_phase("awaiting_user")
            return
        if tool_name == "run_shell":
            self._set_phase("verifying")
            return
        if tool_name in {"list_files", "read_file", "web_fetch"}:
            self._set_phase("inspecting")
            return
        self._set_phase("planning")

    def _set_phase(self, phase: str) -> None:
        normalized = (phase or "").strip().lower() or "running"
        self.state.phase = normalized
        self.session.set_phase(normalized)

    def _set_active_worker(
        self,
        worker: str,
        session_mode: str = "",
        *,
        task_id: str = "",
        profile: str = "",
    ) -> None:
        self.state.active_worker = (worker or "").strip()
        self.state.active_session_mode = (session_mode or "").strip()
        self.session.set_active_worker_runtime(
            worker=self.state.active_worker,
            session_mode=self.state.active_session_mode,
            task_id=task_id or self.session.active_worker_task_id,
            profile=profile or self.session.active_worker_profile,
            can_interrupt=self.session.active_worker_can_interrupt,
        )

    def _set_latest_summary(self, summary: str) -> None:
        normalized = (summary or "").strip()
        if not normalized:
            return
        self.state.latest_summary = normalized
        self.session.set_latest_summary(normalized)

    async def _on_worker_control(self, worker: str, control: WorkerControlRef | None) -> None:
        if control is None:
            self.session.context.pop("_active_worker_control", None)
            self.session.set_active_worker_runtime(
                worker=self.session.active_worker,
                session_mode=self.session.active_session_mode,
                task_id=self.session.active_worker_task_id,
                profile=self.session.active_worker_profile,
                can_interrupt=False,
            )
            return

        self.session.context["_active_worker_control"] = control
        self.session.set_active_worker_runtime(
            worker=worker,
            session_mode=self.session.active_session_mode,
            task_id=control.task_id,
            profile=self.session.active_worker_profile,
            can_interrupt=control.can_interrupt,
        )

    @staticmethod
    def _summarize_result(result: str) -> str:
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict) and payload.get("worker"):
            summary = str(payload.get("summary") or "").strip()
            error = str(payload.get("error") or "").strip()
            artifacts = payload.get("artifacts")
            artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
            parts: list[str] = []
            if summary:
                parts.append(summary)
            if artifact_count:
                parts.append(f"artifacts={artifact_count}")
            if error:
                parts.append(f"error={error}")
            if parts:
                compact_summary = " | ".join(parts)
                if len(compact_summary) > 160:
                    return compact_summary[:160] + "..."
                return compact_summary

        compact = (result or "").strip().replace("\n", " ")
        if len(compact) > 160:
            return compact[:160] + "..."
        return compact or "(empty result)"

    def _has_completion_evidence(self) -> bool:
        successful_worker_runs = [run for run in self.session.worker_runs if run.get("success")]
        if not successful_worker_runs:
            return False

        if self.session.artifacts:
            return True

        latest = successful_worker_runs[-1]
        summary_blob = " ".join(str(latest.get(field) or "") for field in ("summary", "output")).lower()
        return any(
            token in summary_blob
            for token in (
                "pass",
                "passed",
                "completed",
                "generated",
                "created",
                "done",
                "success",
                "verified",
                "ready",
            )
        )

    def _should_attempt_forced_finish(self, iteration: int) -> bool:
        if not self._has_completion_evidence():
            return False
        return iteration >= max(1, self.config.max_iterations - 4)

    async def _try_finalize_from_evidence(self, messages: list[dict[str, Any]], *, reason: str) -> str | None:
        forced_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "You already have enough evidence to conclude this PC task.\n"
                    f"Reason: {reason}\n"
                    "Do not call any more tools. Provide a concise final answer now, including the key result, "
                    "important checks, and relevant artifact paths when available."
                ),
            },
        ]
        try:
            response = await self.provider.chat(messages=forced_messages, tools=None, tool_choice=None)
        except Exception:
            response = None

        final_answer = (response.content or "").strip() if response else ""
        if not final_answer:
            final_answer = self._build_evidence_summary(reason)
        if not final_answer:
            return None

        self.session.context["planner_messages"] = messages + [{"role": "assistant", "content": final_answer}]
        self.state.final_answer = final_answer
        self._set_latest_summary(final_answer)
        return final_answer

    def _build_evidence_summary(self, reason: str) -> str:
        lines: list[str] = ["Task completed based on collected evidence."]
        successful_worker_runs = [run for run in self.session.worker_runs if run.get("success")]
        if successful_worker_runs:
            latest = successful_worker_runs[-1]
            summary = str(latest.get("summary") or "").strip()
            if summary:
                lines.append(summary)
        if self.session.artifacts:
            lines.append("Artifacts:")
            lines.extend(f"- {path}" for path in self.session.artifacts[:8])
            remaining = len(self.session.artifacts) - 8
            if remaining > 0:
                lines.append(f"- ... and {remaining} more")
        if reason:
            lines.append(f"Stop reason: {reason}")
        return "\n".join(lines).strip()
