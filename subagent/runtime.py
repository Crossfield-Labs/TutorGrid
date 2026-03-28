from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from config.subagent_config import SubAgentConfig, load_subagent_config
from providers.registry import ProviderRegistry
from sessions.session_state import PcSessionState
from subagent.capabilities import AwaitUserTool, DelegateOpenCodeTool, ListFilesTool, ReadFileTool, RunShellTool
from subagent.capabilities.agent_delegate import DelegateAgentTool
from subagent.context_builder import ContextBuilder
from subagent.models import RuntimeState, SubstepRecord
from subagent.tool_registry import ToolRegistry
from workers.codex_worker import CodexWorker
from workers.models import WorkerProgressEvent, WorkerResult
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
        self.workers.register(CodexWorker(self.config))
        self.state = RuntimeState(
            workspace=session.workspace or ".",
            goal=session.task or session.goal,
            session_id=session.session_id,
        )
        self._register_tools()

    async def run(self) -> str:
        messages = ContextBuilder.build_messages(self.session)
        for iteration in range(self.config.max_iterations):
            await self.emit_progress(f"PC sub-agent planning iteration {iteration + 1}", min(0.08 + iteration * 0.06, 0.6))
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
                    await self._emit_substep("completed", tool_call.name, self._summarize_result(result))
                self.session.context["planner_messages"] = messages
                continue

            final_answer = (response.content or "").strip()
            if final_answer:
                self.session.context["planner_messages"] = messages + [{"role": "assistant", "content": final_answer}]
                self.state.final_answer = final_answer
                return final_answer

        raise RuntimeError(
            f"PC sub-agent reached the maximum iteration limit ({self.config.max_iterations}) without finishing."
        )

    def _register_tools(self) -> None:
        self.tools.register(ListFilesTool(self.session.workspace))
        self.tools.register(ReadFileTool(self.session.workspace))
        self.tools.register(RunShellTool(self.session.workspace, timeout_seconds=self.config.shell_timeout_seconds))
        self.tools.register(
            DelegateAgentTool(
                workspace=self.session.workspace,
                workers=self.workers,
                on_progress=self._on_worker_progress,
                on_result=self._on_worker_result,
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
        await self.emit_progress(event.message, 0.72)
        if self.emit_substep:
            await self.emit_substep("worker", event.phase or "worker", "progress", event.message)

    async def _on_worker_result(self, result: WorkerResult) -> None:
        record = result.to_record()
        self.state.worker_runs.append(record)
        self.session.worker_runs.append(record)
        self.session.context["worker_runs"] = self.state.worker_runs

        artifact_paths = [artifact.path for artifact in result.artifacts]
        if artifact_paths:
            self.state.artifacts.extend(artifact_paths)
            self.session.artifacts = sorted(set([*self.session.artifacts, *artifact_paths]))

        if self.emit_substep:
            detail = result.summary or result.output[:200] or f"{result.worker} finished"
            await self.emit_substep("worker", result.worker, "completed" if result.success else "failed", detail)

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
