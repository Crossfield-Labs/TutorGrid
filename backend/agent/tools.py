from __future__ import annotations

import json
from typing import Any

import httpx

from backend.rag.service import RagService


def build_tools(*, rag_service: RagService, course_id: str = "", enabled_tools: list[str] | None = None) -> list[dict[str, Any]]:
    allowed = {item.strip().lower() for item in (enabled_tools or ["rag", "tavily"]) if item.strip()}
    tools: list[dict[str, Any]] = []
    if "rag" in allowed:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "rag_query",
                    "description": "Search the course knowledge base and return answer with citations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "course_id": {"type": "string"},
                        },
                        "required": ["question"],
                    },
                },
            }
        )
    if "tavily" in allowed:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "tavily_search",
                    "description": "Search the web for fresh information and provide source URLs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            }
        )
    return tools


async def execute_tool_call(
    *,
    name: str,
    arguments: dict[str, Any],
    rag_service: RagService,
    course_id: str = "",
) -> dict[str, Any]:
    normalized_name = name.strip().lower()
    if normalized_name == "rag_query":
        question = str(arguments.get("question") or "").strip()
        target_course_id = str(arguments.get("course_id") or course_id).strip()
        if not target_course_id:
            return {"error": "course_id is required for rag_query"}
        result = await rag_service.query(course_id=target_course_id, question=question, limit=5)
        citations = []
        for item in result.get("items", []):
            citations.append(
                {
                    "source": str(item.get("fileId") or ""),
                    "page": int(item.get("sourcePage") or 0),
                    "chunk": str(item.get("content") or "")[:300],
                    "score": float(item.get("score") or 0.0),
                }
            )
        return {
            "answer": str(result.get("answer") or ""),
            "citations": citations,
            "raw": result,
        }
    if normalized_name == "tavily_search":
        query = str(arguments.get("query") or "").strip()
        max_results = int(arguments.get("max_results") or 5)
        return await _run_tavily_search(query=query, max_results=max_results)
    return {"error": f"Unsupported tool: {name}"}


async def _run_tavily_search(*, query: str, max_results: int = 5) -> dict[str, Any]:
    api_key = ""
    try:
        from backend.config import load_config

        config = load_config()
        api_key = config.planner.api_key if "tavily" in config.planner.api_base.lower() else ""
    except Exception:
        api_key = ""
    # Env is the canonical source for Tavily.
    import os

    env_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if env_key:
        api_key = env_key
    if not api_key:
        return await _duckduckgo_fallback(query=query, max_results=max_results, reason="TAVILY_API_KEY is not configured")

    payload = {
        "query": query,
        "max_results": max(1, min(max_results, 8)),
        "search_depth": "advanced",
        "include_answer": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post("https://api.tavily.com/search", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("results", []):
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "content": str(item.get("content") or "")[:500],
                "score": float(item.get("score") or 0.0),
            }
        )
    return {"answer": str(data.get("answer") or ""), "results": results, "raw": json.loads(json.dumps(data))}


async def _duckduckgo_fallback(*, query: str, max_results: int = 5, reason: str = "") -> dict[str, Any]:
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get("https://api.duckduckgo.com/", params=params)
        response.raise_for_status()
        data = response.json()
    results: list[dict[str, Any]] = []
    abstract_url = str(data.get("AbstractURL") or "").strip()
    abstract_text = str(data.get("AbstractText") or "").strip()
    if abstract_url or abstract_text:
        results.append(
            {
                "title": str(data.get("Heading") or query),
                "url": abstract_url,
                "content": abstract_text[:500],
                "score": 0.5,
            }
        )
    for topic in data.get("RelatedTopics", [])[: max_results - len(results)]:
        if not isinstance(topic, dict):
            continue
        topic_url = str(topic.get("FirstURL") or "").strip()
        topic_text = str(topic.get("Text") or "").strip()
        if not topic_url and not topic_text:
            continue
        results.append({"title": topic_text[:80], "url": topic_url, "content": topic_text[:500], "score": 0.4})
    return {
        "answer": abstract_text[:500],
        "results": results[:max_results],
        "fallback": "duckduckgo",
        "warning": reason,
        "raw": data,
    }
