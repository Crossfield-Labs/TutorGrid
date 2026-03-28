from __future__ import annotations

import asyncio
import locale
import os
from pathlib import Path

from runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from sessions.session_state import PcSessionState


class ShellRunner(BaseRunner):
    async def run(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        workspace = Path(session.workspace or os.getcwd())
        workspace.mkdir(parents=True, exist_ok=True)

        if self._needs_user_confirmation(session.task):
            user_reply = await await_user(
                "PC shell task needs confirmation before continuing. Reply with continue, cancel, or extra instructions.",
                "text",
            )
            lowered_reply = user_reply.strip().lower()
            if lowered_reply in {"cancel", "stop", "abort"}:
                raise RuntimeError("User cancelled the PC shell task")
            if user_reply.strip():
                session.context["user_confirmation"] = user_reply.strip()

        command = session.context.get("command") or self._build_command(session.task, workspace)
        await emit_progress(f"Running PowerShell command in {workspace}", 0.12)
        await emit_progress(command, 0.18)

        process = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-Command",
            self._wrap_command_with_utf8(command),
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        captured: list[str] = []
        if process.stdout is not None:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = self._decode_output(line).rstrip()
                if not text:
                    continue
                captured.append(text)
                await emit_progress(text, None)

        exit_code = await process.wait()
        output = "\n".join(captured).strip()
        if exit_code != 0:
            raise RuntimeError(output or f"PowerShell exited with code {exit_code}")

        if output:
            return output
        return f"Shell task completed in {workspace}"

    def _build_command(self, task: str, workspace: Path) -> str:
        lowered = task.lower()
        workspace_literal = str(workspace).replace("'", "''")
        if any(token in lowered for token in ("目录", "结构", "list", "tree", "folder", "workspace")):
            return (
                f"Set-Location '{workspace_literal}'; "
                "Get-ChildItem -Force | Select-Object Mode,Name,Length | Format-Table -AutoSize | Out-String -Width 200"
            )
        if any(token in lowered for token in ("python", "版本", "version", "环境", "env")):
            return (
                f"Set-Location '{workspace_literal}'; "
                "$PSVersionTable.PSVersion.ToString(); "
                "python --version; "
                "Get-ChildItem -Force | Select-Object Mode,Name,Length | Format-Table -AutoSize | Out-String -Width 200"
            )
        return (
            f"Set-Location '{workspace_literal}'; "
            "Get-Location; "
            "Get-ChildItem -Force | Select-Object Mode,Name,Length | Format-Table -AutoSize | Out-String -Width 200"
        )

    def _needs_user_confirmation(self, task: str) -> bool:
        lowered = task.lower()
        return any(
            token in lowered
            for token in (
                "先问我",
                "需要确认",
                "ask me",
                "confirm first",
                "before continuing",
            )
        )

    def _wrap_command_with_utf8(self, command: str) -> str:
        return (
            "$OutputEncoding = [Console]::OutputEncoding = "
            "[System.Text.UTF8Encoding]::new($false); "
            f"{command}"
        )

    def _decode_output(self, data: bytes) -> str:
        encodings = [
            "utf-8",
            locale.getpreferredencoding(False),
            "gbk",
            "cp936",
        ]
        for encoding in encodings:
            if not encoding:
                continue
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
