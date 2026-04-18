from __future__ import annotations

from typing import Any

try:
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
except ImportError:  # pragma: no cover
    AIMessage = BaseMessage = HumanMessage = SystemMessage = ToolMessage = None


def serialize_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for message in messages:
        kind = getattr(message, "type", "") or ""
        role = "assistant" if kind == "ai" else "tool" if kind == "tool" else "user" if kind == "human" else "system"
        payload = {"role": role, "content": str(getattr(message, "content", ""))}
        tool_call_id = getattr(message, "tool_call_id", "")
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
        serialized.append(payload)
    return serialized


def deserialize_messages(history: list[dict[str, Any]]) -> list[BaseMessage]:
    if SystemMessage is None:
        return []

    messages: list[BaseMessage] = []
    for item in history:
        role = str(item.get("role") or "user").lower()
        content = str(item.get("content") or "")
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "tool":
            messages.append(ToolMessage(content=content, tool_call_id=str(item.get("tool_call_id") or "tool")))
        elif role == "system":
            messages.append(SystemMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages
