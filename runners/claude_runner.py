from __future__ import annotations

import asyncio
from pathlib import Path

from runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from sessions.session_state import PcSessionState


class ClaudeRunner(BaseRunner):
    async def run(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        workspace = Path(session.workspace or ".").resolve()
        prompt = session.task or session.goal
        if not prompt.strip():
            raise RuntimeError("Claude runner received an empty task")

        await emit_progress("Starting Claude CLI", 0.12)

        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                prompt,
                "--dangerously-skip-permissions",
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Claude CLI is not installed or not on PATH. "
                "Step 1 can still be accepted with shell_runner."
            ) from exc

        captured: list[str] = []
        if process.stdout is not None:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if not text:
                    continue
                captured.append(text)
                await emit_progress(text, None)

        exit_code = await process.wait()
        output = "\n".join(captured).strip()
        if exit_code != 0:
            raise RuntimeError(output or f"Claude CLI exited with code {exit_code}")

        return output or "Claude CLI completed successfully"
