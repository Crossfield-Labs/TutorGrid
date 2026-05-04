from __future__ import annotations

import json
import re
import traceback
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
        allowed_tools = self._normalize_enabled_tools(enabled_tools)
        messages = self._build_messages(message=message, course_id=course_id, context=context)
        tools = build_tools(rag_service=self.rag_service, course_id=course_id, enabled_tools=list(allowed_tools))
        tools_called: list[str] = []
        citations: list[dict[str, Any]] = []
        search_results: list[dict[str, Any]] = []
        fallback_answer = ""
        prefetch_used = False

        if self._should_use_rag_first(message=message, course_id=course_id, allowed_tools=allowed_tools):
            prefetch_used = True
            rag_result = await execute_tool_call(
                name="rag_query",
                arguments={"question": message, "course_id": course_id},
                rag_service=self.rag_service,
                course_id=course_id,
            )
            tools_called.append("rag_query")
            rag_citations = rag_result.get("citations", [])
            citations.extend(rag_citations)
            fallback_answer = str(rag_result.get("answer") or self._summarize_rag_result(rag_result))
            await on_event({"type": "tool_call", "tool": "rag", "query": message})
            await on_event({"type": "tool_result", "tool": "rag", "citations": rag_citations})
            messages.append(self._tool_context_message(name="rag_query", result=rag_result))
        elif self._should_use_tavily_first(message=message, allowed_tools=allowed_tools):
            prefetch_used = True
            tavily_result = await execute_tool_call(
                name="tavily_search",
                arguments={"query": message, "max_results": 5},
                rag_service=self.rag_service,
                course_id=course_id,
            )
            tools_called.append("tavily_search")
            search_results = self._search_results_from_tool_result(tavily_result)
            fallback_answer = self._summarize_tavily_result(tavily_result)
            await on_event({"type": "tool_call", "tool": "tavily", "query": message})
            await on_event(
                {
                    "type": "tool_result",
                    "tool": "tavily",
                    "results": search_results[:3],
                    "warning": tavily_result.get("warning", ""),
                    "fallback": tavily_result.get("fallback", ""),
                }
            )
            messages.append(self._tool_context_message(name="tavily_search", result=tavily_result))

        try:
            tools_for_model = [] if prefetch_used else tools
            response = await self.provider.chat(messages=messages, tools=tools_for_model)
            response = await self._resolve_tools_if_needed(
                response=response,
                messages=messages,
                tools=tools_for_model,
                course_id=course_id,
                on_event=on_event,
                tools_called=tools_called,
                citations=citations,
                search_results=search_results,
            )
        except Exception as exc:
            print(f"[ChatAgent] 第一次 LLM 调用失败: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            await on_event({
                "type": "error",
                "stage": "first_call",
                "exception_type": type(exc).__name__,
                "message": str(exc)[:600],
            })
            response = LLMResponse(content=fallback_answer, tool_calls=[], finish_reason="stop", raw={})

        try:
            final_response = await self.provider.chat(messages=messages, tools=None, on_text_delta=on_delta)
            final_content = str(final_response.content or response.content or "")
        except Exception as exc:
            print(f"[ChatAgent] 流式 LLM 调用失败: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            await on_event({
                "type": "error",
                "stage": "stream_call",
                "exception_type": type(exc).__name__,
                "message": str(exc)[:600],
            })
            err_hint = f"[LLM 调用失败 · {type(exc).__name__}: {str(exc)[:200]}]"
            final_content = fallback_answer or str(response.content or err_hint)
            await on_delta(final_content)
        return {
            "session_id": session_id,
            "content": final_content,
            "tools_called": tools_called,
            "citations": citations,
            "search_results": search_results,
        }

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
        search_results: list[dict[str, Any]],
    ) -> LLMResponse:
        current = response
        max_turns = 4
        for _ in range(max_turns):
            if not current.tool_calls:
                return current
            assistant_message: dict[str, Any] = {"role": "assistant", "content": current.content or ""}
            reasoning_content = _extract_reasoning_content(current.raw)
            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                }
                for call in current.tool_calls
            ]
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content
            messages.append(assistant_message)
            for call in current.tool_calls:
                await on_event(
                    {
                        "type": "tool_call",
                        "tool": call.name,
                        "query": call.arguments.get("question") or call.arguments.get("query") or "",
                    }
                )
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
                    tavily_results = self._search_results_from_tool_result(result)
                    search_results.extend(tavily_results)
                    await on_event(
                        {
                            "type": "tool_result",
                            "tool": "tavily",
                            "results": tavily_results[:3],
                            "warning": result.get("warning", ""),
                            "fallback": result.get("fallback", ""),
                        }
                    )
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

    def _build_messages(
        self,
        *,
        message: str,
        course_id: str = "",
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "你是学生的 Copilot 副驾驶，目标是帮助理解和整理知识，而不是替代学习。"
            "回答要准确、简洁、可执行；当信息不充分时要明确说明。"
            "如果是课程知识问题，优先使用 rag_query。"
            "如果是时效性问题（最新、近期、新闻、政策更新、趋势），优先使用 tavily_search。"
            "引用工具结果时要说明依据，不要编造来源。"
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

    def _should_use_rag_first(self, *, message: str, course_id: str, allowed_tools: set[str]) -> bool:
        return "rag" in allowed_tools and bool(course_id.strip()) and not self._should_use_tavily_first(
            message=message,
            allowed_tools=allowed_tools,
        )

    def _should_use_tavily_first(self, *, message: str, allowed_tools: set[str]) -> bool:
        if "tavily" not in allowed_tools:
            return False
        text = message.strip().lower()
        if not text:
            return False
        patterns = [
            r"最新",
            r"最近",
            r"今日",
            r"今天",
            r"本周",
            r"今年",
            r"新闻",
            r"更新",
            r"现状",
            r"趋势",
            r"联网",
            r"搜索",
            r"查一下",
            r"搜一下",
            r"latest",
            r"recent",
            r"news",
            r"update",
            r"current",
            r"trend",
            r"search",
            r"web",
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    def _summarize_rag_result(self, result: dict[str, Any]) -> str:
        citations = result.get("citations", [])
        if not isinstance(citations, list) or not citations:
            return "未在课程知识库中检索到可用片段。"
        chunks = [str(item.get("chunk") or "").strip() for item in citations[:3] if isinstance(item, dict)]
        chunks = [item for item in chunks if item]
        return "检索到的课程片段：\n" + "\n".join(f"- {item}" for item in chunks)

    def _summarize_tavily_result(self, result: dict[str, Any]) -> str:
        answer = str(result.get("answer") or "").strip()
        if answer:
            return answer
        rows = result.get("results", [])
        if not isinstance(rows, list) or not rows:
            warning = str(result.get("warning") or "").strip()
            return f"已尝试联网检索，但未获得可用结果。{warning}".strip()
        lines = []
        for item in rows[:3]:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or "").strip()
            lines.append(f"- {title}: {content[:120]} {url}".strip())
        return "检索结果：\n" + "\n".join(lines)

    def _search_results_from_tool_result(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        rows = result.get("results", [])
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            normalized.append(
                {
                    "title": str(item.get("title") or url).strip(),
                    "url": url,
                    "content": str(item.get("content") or "").strip(),
                    "score": float(item.get("score") or 0.0),
                }
            )
        return normalized

    def _tool_context_message(self, *, name: str, result: dict[str, Any]) -> dict[str, str]:
        return {
            "role": "system",
            "content": (
                f"工具 `{name}` 已经返回以下 JSON 结果。请把它作为有依据的上下文回答用户，不要编造来源：\n"
                f"{json.dumps(result, ensure_ascii=False)}"
            ),
        }

    def _normalize_enabled_tools(self, enabled_tools: list[str] | None) -> set[str]:
        return {item.strip().lower() for item in (enabled_tools or ["rag", "tavily"]) if item.strip()}


def _extract_reasoning_content(raw_response: Any) -> str:
    if not isinstance(raw_response, dict):
        return ""
    choices = raw_response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("reasoning_content") or "")
