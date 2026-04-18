from __future__ import annotations

import asyncio
from typing import Any

from orchestrator.runtime.state import RuntimeState


async def tools_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    tool_map = dict(runtime_context.get("tool_map") or {})
    planned_calls = list(next_state.get("planned_tool_calls") or [])
    executed_results = list(next_state.get("tool_results") or [])

    for call in planned_calls:
        tool_name = str(call.get("tool") or "").strip()
        arguments = dict(call.get("arguments") or {})
        tool = tool_map.get(tool_name)
        if tool is None:
            executed_results.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": f"Error: tool '{tool_name}' is not registered.",
                }
            )
            continue

        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(arguments)
        else:
            result = tool.invoke(arguments)
            if asyncio.iscoroutine(result):
                result = await result
        executed_results.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "result": str(result),
            }
        )

    next_state["phase"] = "tool_execution"
    next_state["tool_results"] = executed_results
    next_state["planned_tool_calls"] = []
    next_state["last_progress_message"] = f"Executed {len(planned_calls)} tool call(s)."
    return next_state
