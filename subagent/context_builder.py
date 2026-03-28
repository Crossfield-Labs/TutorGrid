from __future__ import annotations

from typing import Any

from sessions.session_state import PcSessionState


class ContextBuilder:
    @staticmethod
    def build_system_prompt(session: PcSessionState) -> str:
        workspace = session.workspace or "."
        return f"""You are MetaAgent's PC sub-agent runtime.

You are not the user-facing primary agent. You are the computer-side sub-agent responsible for carrying out PC tasks safely and efficiently.

Workspace:
{workspace}

Core rules:
- Use tools to inspect the workspace before making claims.
- Prefer list/read tools before shell when they are sufficient.
- Use shell for commands, but stay focused and concise.
- If the task requires a stronger coding backend, call the delegate_agent tool.
- Prefer worker='opencode' for concrete implementation, patching, scaffolding, and editing tasks.
- Prefer worker='codex' for code review, structured analysis, diagnosis, and explanation-heavy tasks.
- If the user explicitly names a backend, honor that preference.
- If one backend fails or looks unsuitable, try the other backend once before giving up.
- If you need the user's decision, call the await_user tool instead of guessing.
- After enough evidence is collected, stop with a concise final answer.
- Do not invent files, outputs, or command results.
- Be explicit about what you found and what you changed.
"""

    @staticmethod
    def build_messages(session: PcSessionState) -> list[dict[str, Any]]:
        system_prompt = ContextBuilder.build_system_prompt(session)
        history = list(session.context.get("planner_messages") or [])
        if history:
            return [{"role": "system", "content": system_prompt}, *history]
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": session.task or session.goal},
        ]

    @staticmethod
    def append_tool_result(
        messages: list[dict[str, Any]],
        *,
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": result,
            }
        )
        return messages

    @staticmethod
    def append_assistant_message(
        messages: list[dict[str, Any]],
        *,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        entry: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        messages.append(entry)
        return messages
