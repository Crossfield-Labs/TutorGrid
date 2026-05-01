from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from backend.config import load_config
from backend.providers.base import LLMResponse
from backend.providers.registry import ProviderRegistry
from backend.rag.service import RagService

from .tools import build_tools, execute_tool_call


class ChatAgent:
    def __init__(self, *, rag_service: RagService | None = None) -> None:
        self.config = load_config()
        self.provider = ProviderRegistry.create(self.config.planner)
        self.rag_service = rag_service or RagService()

    async def stream_chat(
        self,
        *,
        message: str,
        session_id: str,
        course_id: str = "",
        context: dict[str, Any] | None = None,
        enabled_tools: list[str] | None = None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        on_delta: Callable[[str], Awaitable[None]],
    ) -> dict[str, Any]:
        messages = self._build_messages(message=message, course_id=course_id, context=context)
        tools = build_tools(rag_service=self.rag_service, course_id=course_id, enabled_tools=enabled_tools)
        tools_called: list[str] = []
        citations: list[dict[str, Any]] = []
        fallback_answer = ""
        if self._should_use_rag_first(message=message, course_id=course_id):
            rag_result = await execute_tool_call(
                name="rag_query",
                arguments={"question": message, "course_id": course_id},
                rag_service=self.rag_service,
                course_id=course_id,
            )
            tools_called.append("rag_query")
            rag_citations = rag_result.get("citations", [])
            citations.extend(rag_citations)
            fallback_answer = str(rag_result.get("answer") or "")
            await on_event({"type": "tool_call", "tool": "rag", "query": message})
            await on_event({"type": "tool_result", "tool": "rag", "citations": rag_citations})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "prefetch_rag",
                    "name": "rag_query",
                    "content": json.dumps(rag_result, ensure_ascii=False),
                }
            )
        elif self._should_use_tavily_first(message):
            tavily_result = await execute_tool_call(
                name="tavily_search",
                arguments={"query": message, "max_results": 5},
                rag_service=self.rag_service,
                course_id=course_id,
            )
            tools_called.append("tavily_search")
            fallback_answer = self._summarize_tavily_result(tavily_result)
            await on_event({"type": "tool_call", "tool": "tavily", "query": message})
            await on_event({"type": "tool_result", "tool": "tavily", "results": tavily_result.get("results", [])[:3]})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "prefetch_tavily",
                    "name": "tavily_search",
                    "content": json.dumps(tavily_result, ensure_ascii=False),
                }
            )
        # First round: allow model to decide tool usage.
        try:
            response = await self.provider.chat(messages=messages, tools=tools)
            response = await self._resolve_tools_if_needed(
                response=response,
                messages=messages,
                tools=tools,
                course_id=course_id,
                on_event=on_event,
                tools_called=tools_called,
                citations=citations,
            )
        except Exception:
            response = LLMResponse(content=fallback_answer, tool_calls=[], finish_reason="stop", raw={})

        # Stream the final answer.
        try:
            final_response = await self.provider.chat(messages=messages, tools=None, on_text_delta=on_delta)
            if final_response.content and not isinstance(final_response.content, str):
                final_response.content = str(final_response.content)
            final_content = str(final_response.content or response.content or "")
        except Exception:
            final_content = fallback_answer or str(response.content or "当前无法调用LLM，请稍后重试。")
            await on_delta(final_content)
        return {
            "session_id": session_id,
            "content": final_content,
            "tools_called": tools_called,
            "citations": citations,
        }

    def _summarize_tavily_result(self, result: dict[str, Any]) -> str:
        answer = str(result.get("answer") or "").strip()
        if answer:
            return answer
        rows = result.get("results", [])
        if not isinstance(rows, list) or not rows:
            return "已尝试联网检索，但未获得可用结果。"
        lines = []
        for item in rows[:3]:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or "").strip()
            lines.append(f"- {title}: {content[:120]} {url}".strip())
        return "检索结果：\n" + "\n".join(lines)

    def _should_use_rag_first(self, *, message: str, course_id: str) -> bool:
        return bool(course_id.strip()) and not self._should_use_tavily_first(message)

    def _should_use_tavily_first(self, message: str) -> bool:
        text = message.strip().lower()
        if not text:
            return False
        patterns = [r"最新", r"最近", r"今日", r"本周", r"今年", r"news", r"latest", r"recent", r"update"]
        return any(re.search(pattern, text) for pattern in patterns)

    async def _resolve_tools_if_needed(
        self,
        *,
        response: LLMResponse,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        course_id: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        tools_called: list[str],
        citations: list[dict[str, Any]],
    ) -> LLMResponse:
        current = response
        max_turns = 4
        for _ in range(max_turns):
            if not current.tool_calls:
                return current
            assistant_message: dict[str, Any] = {"role": "assistant", "content": current.content or ""}
            if current.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                    }
                    for call in current.tool_calls
                ]
            messages.append(assistant_message)
            for call in current.tool_calls:
                await on_event({"type": "tool_call", "tool": call.name, "query": call.arguments.get("question") or call.arguments.get("query") or ""})
                result = await execute_tool_call(
                    name=call.name,
                    arguments=call.arguments,
                    rag_service=self.rag_service,
                    course_id=course_id,
                )
                tools_called.append(call.name)
                if call.name == "rag_query":
                    rag_citations = result.get("citations", [])
                    citations.extend(rag_citations)
                    await on_event({"type": "tool_result", "tool": "rag", "citations": rag_citations})
                if call.name == "tavily_search":
                    await on_event({"type": "tool_result", "tool": "tavily", "results": result.get("results", [])[:3]})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            current = await self.provider.chat(messages=messages, tools=tools)
        return current

    def _build_messages(self, *, message: str, course_id: str = "", context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        system_prompt = (
            "你是学生的 Copilot 副驾驶，目标是帮助理解与整理，而不是替代学习。"
            "回答要准确、简洁、可执行；当信息不充分时明确说明。"
            "如果是课程知识问题，优先使用 rag_query。"
            "如果是时效性问题（最新、近期、新闻、政策更新），优先使用 tavily_search。"
        )
        if course_id:
            system_prompt += f" 当前会话课程ID: {course_id}。"
        if context:
            recent = context.get("recent_paragraphs") or []
            if isinstance(recent, list) and recent:
                system_prompt += " 文档上下文: " + " | ".join(str(item)[:120] for item in recent[:3])
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]
