from __future__ import annotations

from config.subagent_config import load_subagent_config
from runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from sessions.session_state import PcSessionState
from workers.codex_worker import CodexWorker
from workers.models import WorkerProgressEvent


class CodexRunner(BaseRunner):
    async def run(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        task = (session.task or session.goal).strip()
        if not task:
            raise RuntimeError("Codex runner received an empty task.")

        worker = CodexWorker(load_subagent_config())

        async def on_progress(event: WorkerProgressEvent) -> None:
            await emit_progress(event.message, None)

        await emit_progress("Starting Codex CLI", 0.12)
        result = await worker.run(
            task=task,
            workspace=session.workspace,
            on_progress=on_progress,
        )
        if not result.success:
            raise RuntimeError(result.error or result.summary or "Codex CLI failed.")
        return result.output or result.summary or "Codex CLI completed successfully"
