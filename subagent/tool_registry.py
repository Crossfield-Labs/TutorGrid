from __future__ import annotations

from typing import Any

from subagent.tool_base import SubAgentTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, SubAgentTool] = {}

    def register(self, tool: SubAgentTool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found."
        try:
            return await tool.execute(**arguments)
        except Exception as error:
            return f"Error while executing tool '{name}': {error.__class__.__name__}: {error}"
