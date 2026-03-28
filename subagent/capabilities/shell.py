from __future__ import annotations

import asyncio
import locale
import re
from pathlib import Path
from typing import Any

from subagent.tool_base import SubAgentTool


DENY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "Blocked destructive rm -rf command."),
    (re.compile(r"\bremove-item\b.*\b-recurse\b", re.IGNORECASE), "Blocked recursive Remove-Item command."),
    (re.compile(r"\brd\s+/s\s+/q\b", re.IGNORECASE), "Blocked destructive rd /s /q command."),
    (re.compile(r"\bdel\b.*\s/f\b.*\s/s\b.*\s/q\b", re.IGNORECASE), "Blocked destructive del /f /s /q command."),
    (re.compile(r"\bformat\b", re.IGNORECASE), "Blocked disk format command."),
    (re.compile(r"\bmkfs\b", re.IGNORECASE), "Blocked filesystem formatting command."),
    (re.compile(r"\bdiskpart\b", re.IGNORECASE), "Blocked diskpart command."),
    (re.compile(r"\bshutdown\b", re.IGNORECASE), "Blocked shutdown command."),
    (re.compile(r"\breboot\b", re.IGNORECASE), "Blocked reboot command."),
    (re.compile(r"\bpoweroff\b", re.IGNORECASE), "Blocked poweroff command."),
)


class RunShellTool(SubAgentTool):
    def __init__(self, workspace: str, timeout_seconds: int = 90) -> None:
        self.workspace = Path(workspace or ".").resolve()
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "run_shell"

    @property
    def description(self) -> str:
        return "Run a shell command inside the workspace. Use for inspection or execution when file tools are insufficient."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run."},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, **kwargs: Any) -> str:
        denied_reason = self._deny_reason(command)
        if denied_reason:
            return f"Error: {denied_reason}"

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Error: Command timed out after {self.timeout_seconds} seconds"

        stdout_text = self._decode(stdout)
        stderr_text = self._decode(stderr)
        result = stdout_text.strip()
        if stderr_text.strip():
            result = f"{result}\n\nSTDERR:\n{stderr_text}".strip()
        return (result if result else "(no output)") + f"\n\nExit code: {process.returncode}"

    @staticmethod
    def _decode(raw: bytes) -> str:
        if not raw:
            return ""
        for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk", "cp936"):
            try:
                return raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _deny_reason(command: str) -> str | None:
        normalized = command.strip()
        for pattern, reason in DENY_PATTERNS:
            if pattern.search(normalized):
                return reason
        return None
