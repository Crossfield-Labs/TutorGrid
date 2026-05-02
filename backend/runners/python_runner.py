from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from backend.config import OrchestratorConfig, load_config
from backend.runners.base import AwaitUserCallback, BaseRunner, MessageEventCallback, ProgressCallback, SubstepCallback
from backend.sessions.state import OrchestratorSessionState
from backend.workers.common import diff_workspace, snapshot_workspace
from backend.workers.models import WorkerResult


class PythonRunner(BaseRunner):
    def __init__(self) -> None:
        self._emit_substep: SubstepCallback | None = None
        self._emit_message_event: MessageEventCallback | None = None

    def set_event_callbacks(
        self,
        *,
        emit_substep: SubstepCallback | None = None,
        emit_message_event: MessageEventCallback | None = None,
    ) -> None:
        self._emit_substep = emit_substep
        self._emit_message_event = emit_message_event

    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        _ = await_user
        config = load_config()
        workspace_path = self._resolve_workspace(session.workspace, config)
        code = self._extract_python_code(session)
        before = snapshot_workspace(workspace_path)

        if not code:
            raise RuntimeError("Python runner requires code in session.context['python_code'] or a fenced ```python block.")

        if self._emit_substep is not None:
            await self._emit_substep("runner", "Python task", "started", "python runner started")

        payload = {
            "messageId": f"{session.session_id}:assistant:python:1",
            "role": "assistant",
            "contentType": "text/markdown",
            "phase": "planning",
        }
        if self._emit_message_event is not None:
            await self._emit_message_event("started", payload)

        await emit_progress(f"Running isolated Python task in {workspace_path}", 0.12)

        try:
            completed = await asyncio.wait_for(
                asyncio.to_thread(
                    subprocess.run,
                    [
                        config.python_command,
                        "-I",
                        "-B",
                        "-u",
                        "-c",
                        code,
                    ],
                    cwd=str(workspace_path),
                    capture_output=True,
                    env=self._build_env(config),
                    timeout=max(1, config.python_runner_timeout_seconds),
                    check=False,
                ),
                timeout=max(1, config.python_runner_timeout_seconds) + 1,
            )
        except (asyncio.TimeoutError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(
                f"Python runner timed out after {config.python_runner_timeout_seconds}s."
            ) from error

        stdout_text = self._truncate_output(completed.stdout, config.python_runner_output_limit_bytes)
        stderr_text = self._truncate_output(completed.stderr, config.python_runner_output_limit_bytes)

        if stdout_text:
            await emit_progress(stdout_text, 0.75)
            if self._emit_message_event is not None:
                await self._emit_message_event("delta", {**payload, "delta": stdout_text})
        if stderr_text:
            await emit_progress(stderr_text, 0.9)

        if completed.returncode != 0:
            raise RuntimeError(stderr_text or stdout_text or f"Python runner exited with code {completed.returncode}")
        after = snapshot_workspace(workspace_path)
        artifacts = diff_workspace(before, after)
        if artifacts:
            artifact_paths = [artifact.path for artifact in artifacts]
            session.artifacts = sorted(set([*session.artifacts, *artifact_paths]))
            artifact_summary = f"{len(artifact_paths)} artifact(s): " + ", ".join(artifact_paths[:3])
            remaining = len(artifact_paths) - 3
            if remaining > 0:
                artifact_summary += f", and {remaining} more"
            session.set_latest_artifact_summary(artifact_summary)
        result_text = stdout_text or "Python runner completed successfully."
        record = WorkerResult(
            worker="python_runner",
            success=True,
            summary=result_text[:240],
            output=result_text,
            artifacts=artifacts,
            metadata={
                "workspace": str(workspace_path),
                "returncode": completed.returncode,
                "python_command": config.python_command,
            },
        ).to_record()
        session.worker_runs.append(record)
        if self._emit_substep is not None:
            await self._emit_substep("runner", "Python task", "completed", result_text)
        if self._emit_message_event is not None:
            await self._emit_message_event(
                "completed",
                {**payload, "content": result_text, "finishReason": "stop"},
            )
        return result_text

    @staticmethod
    def _extract_python_code(session: OrchestratorSessionState) -> str:
        context_code = str(session.context.get("python_code") or "").strip()
        if context_code:
            return context_code

        task = session.task or ""
        marker = "```python"
        if marker in task:
            _, _, remainder = task.partition(marker)
            code, _, _ = remainder.partition("```")
            return code.strip()
        return ""

    @staticmethod
    def _resolve_workspace(workspace: str, config: OrchestratorConfig) -> Path:
        workspace_path = Path(workspace or ".").resolve()
        workspace_path.mkdir(parents=True, exist_ok=True)

        configured_root = str(config.python_runner_workspace_root or "").strip()
        if not configured_root:
            return workspace_path

        allowed_root = Path(configured_root).resolve()
        try:
            workspace_path.relative_to(allowed_root)
        except ValueError as error:
            raise RuntimeError(
                f"Python runner workspace must stay within configured root: {allowed_root}"
            ) from error
        return workspace_path

    @staticmethod
    def _build_env(config: OrchestratorConfig) -> dict[str, str]:
        allowed = {item.strip().upper() for item in config.python_runner_allowed_env if item.strip()}
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in allowed
        }
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUNBUFFERED", "1")
        return env

    @staticmethod
    def _truncate_output(data: bytes, limit_bytes: int) -> str:
        if not data:
            return ""
        limit = max(256, limit_bytes)
        truncated = len(data) > limit
        payload = data[:limit]
        text = payload.decode("utf-8", errors="replace").strip()
        if truncated:
            text = f"{text}\n...[output truncated]"
        return text
