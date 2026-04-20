from __future__ import annotations

from typing import Any

from backend.config import OrchestratorConfig
from backend.llm.messages import deserialize_messages, serialize_messages
from backend.llm.prompts import build_planner_prompt
from backend.providers.base import LLMResponse
from backend.providers.registry import ProviderRegistry


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
    ) -> list[dict[str, Any]]:
        if self.prompt is None:
            return history
        langchain_messages = self.prompt.format_messages(
            goal=goal or task,
            task=task,
            workspace=workspace,
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
    ) -> tuple[list[dict[str, Any]], LLMResponse]:
        messages = self.build_messages(task=task, goal=goal, workspace=workspace, history=history)
        response = await self.provider.chat(messages=messages, tools=tools)
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
        response = await self.provider.chat(messages=messages, tools=None)
        return str(response.content or "").strip()

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


