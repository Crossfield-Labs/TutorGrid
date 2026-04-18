from __future__ import annotations

from pathlib import Path

from orchestrator.runtime.state import RuntimeState


def planning_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    planner = dict(next_state.get("context") or {}).get("planner")
    iteration = int(next_state.get("iteration") or 0) + 1
    next_state["iteration"] = iteration
    next_state["phase"] = "planning"
    next_state["status"] = "RUNNING"
    next_state["messages"] = planner.build_messages(
        task=str(next_state.get("task") or ""),
        goal=str(next_state.get("goal") or ""),
        history=list(next_state.get("messages") or []),
    )
    task = str(next_state.get("task") or "").strip()
    workspace = Path(str(next_state.get("workspace") or ".")).resolve()
    tool_results = list(next_state.get("tool_results") or [])

    if not tool_results:
        next_state["planned_tool_calls"] = [
            {"tool": "list_files", "arguments": {"path": str(workspace)}},
            {"tool": "read_file", "arguments": {"path": str(workspace / "main.py")}},
            {"tool": "read_file", "arguments": {"path": str(workspace / "requirements.txt")}},
        ]
        next_state["last_progress_message"] = (
            f"Planning iteration {iteration} with LangGraph and LangChain; scheduled initial inspection tools."
        )
        return next_state

    summary_lines = [
        f"任务：{task or '（空任务）'}",
        f"工作区：{workspace}",
        "",
        "已执行检查：",
    ]
    for item in tool_results[:5]:
        tool_name = str(item.get("tool") or "tool")
        result_text = str(item.get("result") or "").replace("\n", " ").strip()
        preview = result_text[:220] + ("..." if len(result_text) > 220 else "")
        summary_lines.append(f"- {tool_name}: {preview}")

    next_state["last_progress_message"] = f"Planning iteration {iteration} completed with collected tool evidence."
    next_state["latest_summary"] = "已根据工具结果生成项目初步分析。"
    next_state["final_answer"] = "\n".join(summary_lines).strip()
    return next_state
