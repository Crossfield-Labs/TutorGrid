from __future__ import annotations

import asyncio
from typing import Any
from typing import Awaitable, Callable

from backend.config import OrchestratorConfig
from backend.llm.messages import deserialize_messages, serialize_messages
from backend.llm.prompts import build_planner_prompt
from backend.providers.base import LLMResponse
from backend.providers.registry import ProviderRegistry

FinalAnswerStreamCallback = Callable[[str], Awaitable[None]]


class PlannerRuntime:
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.prompt = build_planner_prompt()
        self.provider = ProviderRegistry.create(config.planner)

    def build_messages(
        self,
        *,
        task: str,
        goal: str,
        workspace: str,
        history: list[dict[str, Any]],
        memory_context: str = "",
    ) -> list[dict[str, Any]]:
        if self.prompt is None:
            if not memory_context.strip():
                return history
            return [
                {"role": "system", "content": memory_context.strip()},
                *history,
            ]
        langchain_messages = self.prompt.format_messages(
            goal=goal or task,
            task=task,
            workspace=workspace,
            memory_context=memory_context.strip(),
            history=deserialize_messages(history),
        )
        return serialize_messages(langchain_messages)

    async def plan(
        self,
        *,
        task: str,
        goal: str,
        workspace: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        memory_context: str = "",
        on_text_delta: FinalAnswerStreamCallback | None = None,
    ) -> tuple[list[dict[str, Any]], LLMResponse]:
        messages = self.build_messages(
            task=task,
            goal=goal,
            workspace=workspace,
            history=history,
            memory_context=memory_context,
        )
        response = await self.provider.chat(messages=messages, tools=tools, on_text_delta=on_text_delta)
        return messages, response

    async def finalize_from_evidence(
        self,
        *,
        task: str,
        goal: str,
        workspace: str,
        history: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        reason: str,
        on_text_delta: FinalAnswerStreamCallback | None = None,
    ) -> str:
        evidence_lines = []
        for item in evidence[:8]:
            tool_name = str(item.get("tool") or "tool")
            result_text = str(item.get("result") or "").strip().replace("\n", " ")
            preview = result_text[:280] + ("..." if len(result_text) > 280 else "")
            evidence_lines.append(f"- {tool_name}: {preview}")

        messages = self.build_messages(task=task, goal=goal, workspace=workspace, history=history)
        messages.append(
            {
                "role": "user",
                "content": (
                    "You already have enough evidence to conclude this task.\n"
                    f"Reason: {reason}\n"
                    "Do not call tools. Provide a concise final answer in Chinese.\n"
                    "Use the collected evidence below:\n"
                    + "\n".join(evidence_lines)
                ),
            }
        )
        response = await self.provider.chat(messages=messages, tools=None, on_text_delta=on_text_delta)
        return str(response.content or "").strip()

    @staticmethod
    async def replay_text_as_stream(
        text: str,
        *,
        on_text_delta: FinalAnswerStreamCallback | None = None,
        chunk_size: int = 24,
    ) -> None:
        if on_text_delta is None or not text:
            return
        for index in range(0, len(text), max(1, chunk_size)):
            await on_text_delta(text[index : index + max(1, chunk_size)])
            await asyncio.sleep(0)

    @staticmethod
    def build_fallback_summary(
        *,
        task: str,
        workspace: str,
        evidence: list[dict[str, Any]],
        reason: str,
    ) -> str:
        lines = [
            f"任务：{task or '（空任务）'}",
            f"工作区：{workspace}",
            "",
            "已收集证据：",
        ]
        if evidence:
            for item in evidence[:8]:
                tool_name = str(item.get("tool") or "tool")
                result_text = str(item.get("result") or "").replace("\n", " ").strip()
                preview = result_text[:240] + ("..." if len(result_text) > 240 else "")
                lines.append(f"- {tool_name}: {preview}")
        else:
            lines.append("- 尚未收集到有效工具结果。")
        if reason:
            lines.extend(["", f"结束原因：{reason}"])
        return "\n".join(lines).strip()


