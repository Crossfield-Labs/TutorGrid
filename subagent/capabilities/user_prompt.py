from __future__ import annotations

from typing import Any, Awaitable, Callable

from subagent.tool_base import SubAgentTool

AwaitUserFn = Callable[[str, str | None], Awaitable[str]]


class AwaitUserTool(SubAgentTool):
    def __init__(self, await_user_fn: AwaitUserFn) -> None:
        self.await_user_fn = await_user_fn

    @property
    def name(self) -> str:
        return "await_user"

    @property
    def description(self) -> str:
        return "Pause execution and ask the user for a decision or missing information."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What the user should answer."},
                "input_mode": {"type": "string", "description": "Usually 'text'."},
            },
            "required": ["message"],
        }

    async def execute(self, message: str, input_mode: str = "text", **kwargs: Any) -> str:
        answer = await self.await_user_fn(message, input_mode)
        return f"User replied: {answer}"
