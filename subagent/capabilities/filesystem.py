from __future__ import annotations

from pathlib import Path
from typing import Any

from subagent.tool_base import SubAgentTool


class _WorkspaceTool(SubAgentTool):
    def __init__(self, workspace: str) -> None:
        self.workspace = Path(workspace or ".").resolve()

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = (self.workspace / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
        if self.workspace not in candidate.parents and candidate != self.workspace:
            raise RuntimeError(f"Path outside workspace is not allowed: {candidate}")
        return candidate


class ListFilesTool(_WorkspaceTool):
    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files and directories inside the workspace. Use this before reading or editing files."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the workspace."},
            },
            "required": [],
        }

    async def execute(self, path: str = ".", **kwargs: Any) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: Path does not exist: {target}"
        entries = []
        for item in sorted(target.iterdir(), key=lambda value: (value.is_file(), value.name.lower())):
            label = "DIR" if item.is_dir() else "FILE"
            size = "" if item.is_dir() else f" ({item.stat().st_size} bytes)"
            entries.append(f"- {label} {item.name}{size}")
        return "\n".join(entries) if entries else "(empty directory)"


class ReadFileTool(_WorkspaceTool):
    _MAX_CHARS = 12000

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a UTF-8 text file from the workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file inside the workspace."},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        target = self._resolve_path(path)
        if not target.exists() or not target.is_file():
            return f"Error: File does not exist: {target}"
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > self._MAX_CHARS:
            omitted = len(content) - self._MAX_CHARS
            content = content[: self._MAX_CHARS] + f"\n\n... ({omitted} chars omitted)"
        return content
