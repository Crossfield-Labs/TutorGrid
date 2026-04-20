from __future__ import annotations

import json
from typing import Any

from backend.llm.messages import append_assistant_message, append_user_message
from backend.runtime.session_sync import sync_session_from_runtime_state
from backend.runtime.state import RuntimeState


async def planning_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    planner = runtime_context.get("planner")
    tool_definitions = list(runtime_context.get("tool_definitions") or [])
    session = runtime_context.get("session")
    memory_service = runtime_context.get("memory_service")
    memory_config = runtime_context.get("memory_config")
    iteration = int(next_state.get("iteration") or 0) + 1
    next_state["iteration"] = iteration
    next_state["phase"] = "planning"
    next_state["status"] = "RUNNING"
    task = str(next_state.get("task") or "").strip()
    goal = str(next_state.get("goal") or task).strip()
    workspace = str(next_state.get("workspace") or ".")
    max_iterations = int(next_state.get("max_iterations") or 8)
    tool_results = list(next_state.get("tool_results") or [])
    tool_events = list(next_state.get("tool_events") or [])
    history = list(next_state.get("messages") or [])

    if session is not None:
        consumed_followups = session.drain_followups()
        for followup in consumed_followups:
            intent = str(followup.get("intent") or "comment").strip().lower() or "comment"
            text = str(followup.get("text") or "").strip()
            target = str(followup.get("target") or "").strip()
            if not text:
                continue
            if intent == "redirect":
                content = (
                    "The user changed direction for the current task.\n"
                    "Treat this as a high-priority update and revise the plan without losing state.\n"
                    f"Direction change: {text}"
                )
            else:
                content = (
                    "The user sent a follow-up message for the current task.\n"
                    "Use it as additional context while continuing the same task.\n"
                    f"Follow-up: {text}"
                )
            if target:
                content += f"\nTarget: {target}"
            history = append_user_message(history, content=content)
            tool_events.append({"tool": "followup", "intent": intent, "target": target, "result": text})
            next_state["latest_summary"] = (
                f"Accepted a direction change: {text}" if intent == "redirect" else f"Accepted a follow-up message: {text}"
            )

    memory_context = ""
    if memory_service is not None and getattr(memory_config, "enabled", True):
        retrieval_scope = str(getattr(memory_config, "retrieval_scope", "global") or "global").strip().lower()
        retrieval_strength = str(getattr(memory_config, "retrieval_strength", "standard") or "standard").strip().lower()
        retrieval_limit = {"conservative": 2, "standard": 4, "aggressive": 6}.get(retrieval_strength, 4)
        memory_context = _build_memory_context(
            memory_service.search(
                query=task or goal,
                limit=retrieval_limit,
                session_id=next_state.get("session_id") if retrieval_scope == "session" else None,
            ),
        )

    messages, response = await planner.plan(
        task=task,
        goal=goal,
        workspace=workspace,
        history=history,
        tools=tool_definitions,
        memory_context=memory_context,
    )
    if response.tool_calls:
        planned_tool_calls = [
            {"id": item.id, "tool": item.name, "arguments": item.arguments}
            for item in response.tool_calls
        ]
        filtered_tool_calls, dropped_duplicates = _filter_duplicate_tool_calls(
            planned_tool_calls,
            tool_events=tool_events,
        )
        if not filtered_tool_calls and dropped_duplicates and tool_results and _has_completion_evidence(next_state):
            forced_final = await planner.finalize_from_evidence(
                task=task,
                goal=goal,
                workspace=workspace,
                history=messages,
                evidence=tool_results,
                reason="The planner only suggested duplicate tool calls, and the existing evidence is already sufficient.",
            )
            final_text = forced_final or planner.build_fallback_summary(
                task=task,
                workspace=workspace,
                evidence=tool_results,
                reason="Duplicate tool calls were suppressed because the same evidence had already been collected.",
            )
            next_state["messages"] = append_assistant_message(messages, content=final_text)
            next_state["planned_tool_calls"] = []
            next_state["tool_events"] = tool_events + [
                {"tool": "dedupe", "result": f"Suppressed {dropped_duplicates} duplicate tool call(s)."}
            ]
            next_state["latest_summary"] = final_text
            next_state["last_progress_message"] = (
                f"Planning iteration {iteration} finalized after suppressing {dropped_duplicates} duplicate tool call(s)."
            )
            next_state["final_answer"] = final_text
            next_state["stop_reason"] = "completed_after_duplicate_suppression"
            await sync_session_from_runtime_state(
                next_state,
                emit_progress=runtime_context.get("emit_progress"),
                progress=0.9,
            )
            return next_state

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
        next_state["messages"] = append_assistant_message(
            messages,
            content=response.content,
            tool_calls=assistant_tool_calls,
        )
        next_state["planned_tool_calls"] = filtered_tool_calls
        next_state["tool_events"] = tool_events + (
            [{"tool": "dedupe", "result": f"Suppressed {dropped_duplicates} duplicate tool call(s)."}]
            if dropped_duplicates
            else []
        )
        next_state["worker_sessions"] = dict(session.worker_sessions if session is not None else next_state.get("worker_sessions") or {})
        next_state["last_progress_message"] = (
            f"Planning iteration {iteration} scheduled {len(filtered_tool_calls)} tool call(s)."
        )
        if dropped_duplicates:
            next_state["latest_summary"] = f"Suppressed {dropped_duplicates} duplicate tool call(s)."
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=min(0.08 + iteration * 0.06, 0.55),
        )
        return next_state

    if not tool_results and iteration < max(2, max_iterations):
        response_text = str(response.content or "").strip()
        if _should_accept_direct_answer(task=task, goal=goal, response_text=response_text):
            final_text = response_text
            next_state["messages"] = append_assistant_message(messages, content=final_text)
            next_state["planned_tool_calls"] = []
            next_state["tool_events"] = tool_events
            next_state["worker_sessions"] = dict(
                session.worker_sessions if session is not None else next_state.get("worker_sessions") or {}
            )
            next_state["last_progress_message"] = f"Planning iteration {iteration} answered directly without tools."
            next_state["latest_summary"] = final_text
            next_state["final_answer"] = final_text
            next_state["stop_reason"] = "completed_direct_answer"
            await sync_session_from_runtime_state(
                next_state,
                emit_progress=runtime_context.get("emit_progress"),
                progress=0.9,
            )
            return next_state
        if not _should_bootstrap_inspection(task=task, goal=goal):
            final_text = response_text or planner.build_fallback_summary(
                task=task,
                workspace=workspace,
                evidence=tool_results,
                reason="The planner did not request any tools, and the task does not require repository inspection.",
            )
            next_state["messages"] = append_assistant_message(messages, content=final_text)
            next_state["planned_tool_calls"] = []
            next_state["tool_events"] = tool_events
            next_state["worker_sessions"] = dict(
                session.worker_sessions if session is not None else next_state.get("worker_sessions") or {}
            )
            next_state["last_progress_message"] = (
                f"Planning iteration {iteration} answered directly without repository inspection."
            )
            next_state["latest_summary"] = final_text
            next_state["final_answer"] = final_text
            next_state["stop_reason"] = "completed_without_bootstrap"
            await sync_session_from_runtime_state(
                next_state,
                emit_progress=runtime_context.get("emit_progress"),
                progress=0.9,
            )
            return next_state
        next_state["messages"] = append_assistant_message(messages, content=response.content)
        next_state["planned_tool_calls"] = [
            {"id": "bootstrap-list-files", "tool": "list_files", "arguments": {"path": "."}},
            {"id": "bootstrap-read-main", "tool": "read_file", "arguments": {"path": "main.py"}},
            {"id": "bootstrap-read-readme", "tool": "read_file", "arguments": {"path": "README.md"}},
        ]
        next_state["tool_events"] = tool_events
        next_state["worker_sessions"] = dict(session.worker_sessions if session is not None else next_state.get("worker_sessions") or {})
        next_state["last_progress_message"] = (
            f"Planning iteration {iteration} produced no tool calls; scheduled bootstrap inspection tools."
        )
        next_state["latest_summary"] = str(response.content or "").strip()
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=min(0.08 + iteration * 0.06, 0.55),
        )
        return next_state

    if tool_results and _should_attempt_forced_finish(next_state, iteration, max_iterations):
        forced_final = await planner.finalize_from_evidence(
            task=task,
            goal=goal,
            workspace=workspace,
            history=messages,
            evidence=tool_results,
            reason="Enough evidence has already been collected to conclude the task.",
        )
        if forced_final:
            next_state["messages"] = append_assistant_message(messages, content=forced_final)
            next_state["last_progress_message"] = f"Planning iteration {iteration} finalized from collected evidence."
            next_state["latest_summary"] = forced_final
            next_state["final_answer"] = forced_final
            next_state["stop_reason"] = "completed_from_evidence"
            next_state["tool_events"] = tool_events
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.9,
        )
        return next_state

    if iteration >= max_iterations:
        fallback = planner.build_fallback_summary(
            task=task,
            workspace=workspace,
            evidence=tool_results,
            reason=f"Reached max iterations ({max_iterations}) without a final answer.",
        )
        next_state["messages"] = append_assistant_message(messages, content=fallback)
        next_state["last_progress_message"] = f"Planning iteration {iteration} forced completion at max iterations."
        next_state["latest_summary"] = fallback
        next_state["final_answer"] = fallback
        next_state["stop_reason"] = "max_iterations_finalized"
        next_state["tool_events"] = tool_events
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.9,
        )
        return next_state

    next_state["messages"] = append_assistant_message(messages, content=response.content)
    next_state["last_progress_message"] = f"Planning iteration {iteration} produced a final response."
    next_state["latest_summary"] = str(response.content or "").strip()
    next_state["final_answer"] = str(response.content or "").strip()
    next_state["stop_reason"] = "completed"
    next_state["tool_events"] = tool_events
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.9,
    )
    return next_state


def _has_completion_evidence(state: RuntimeState) -> bool:
    worker_runs = [run for run in list(state.get("worker_runs") or []) if run.get("success")]
    if worker_runs:
        if state.get("artifacts"):
            return True
        latest = worker_runs[-1]
        summary_blob = " ".join(str(latest.get(field) or "") for field in ("summary", "output")).lower()
        if any(
            token in summary_blob
            for token in ("pass", "passed", "completed", "generated", "created", "done", "success", "verified", "ready")
        ):
            return True

    tool_results = list(state.get("tool_results") or [])
    if not tool_results:
        return False
    non_empty_results = [str(item.get("result") or "").strip() for item in tool_results]
    return any(bool(item) for item in non_empty_results)


def _should_attempt_forced_finish(state: RuntimeState, iteration: int, max_iterations: int) -> bool:
    if not _has_completion_evidence(state):
        return False
    return iteration >= max(1, max_iterations - 4)


def _filter_duplicate_tool_calls(
    planned_tool_calls: list[dict[str, Any]],
    *,
    tool_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    seen_signatures = {_tool_signature(item.get("tool"), item.get("arguments")) for item in tool_events if item.get("tool")}
    filtered: list[dict[str, Any]] = []
    dropped = 0
    local_signatures: set[str] = set()

    for call in planned_tool_calls:
        signature = _tool_signature(call.get("tool"), call.get("arguments"))
        if signature in seen_signatures or signature in local_signatures:
            dropped += 1
            continue
        filtered.append(call)
        local_signatures.add(signature)
    return filtered, dropped


def _tool_signature(tool_name: Any, arguments: Any) -> str:
    normalized_arguments = arguments if isinstance(arguments, dict) else {"value": arguments}
    return f"{str(tool_name or '').strip().lower()}::{json.dumps(normalized_arguments, ensure_ascii=False, sort_keys=True)}"


def _should_accept_direct_answer(*, task: str, goal: str, response_text: str) -> bool:
    if not response_text or len(response_text) < 80:
        return False
    prompt_text = f"{task}\n{goal}".strip().lower()
    direct_answer_signals = (
        "讲解",
        "解释",
        "介绍",
        "什么是",
        "如何理解",
        "原理",
        "思路",
        "算法",
        "区别",
        "why",
        "what is",
        "explain",
    )
    return any(signal in prompt_text for signal in direct_answer_signals)


def _should_bootstrap_inspection(*, task: str, goal: str) -> bool:
    prompt_text = f"{task}\n{goal}".strip().lower()
    inspection_signals = (
        "项目",
        "仓库",
        "代码",
        "源码",
        "目录",
        "文件",
        "模块",
        "readme",
        "server",
        "runtime",
        "backend",
        "frontend",
        "repo",
        "repository",
        "codebase",
        "project",
        "source",
        "file",
        "folder",
        "module",
    )
    return any(signal in prompt_text for signal in inspection_signals)


def _build_memory_context(results: list[Any]) -> str:
    if not results:
        return "No relevant long-term memory was retrieved."
    lines = ["Relevant long-term memory:"]
    for item in results[:4]:
        title = str(getattr(item, "title", "") or "记忆片段").strip()
        content = str(getattr(item, "content", "") or "").strip().replace("\n", " ")
        score = float(getattr(item, "score", 0.0) or 0.0)
        preview = content[:240] + ("..." if len(content) > 240 else "")
        lines.append(f"- {title} (score={score:.3f}): {preview}")
    return "\n".join(lines)


