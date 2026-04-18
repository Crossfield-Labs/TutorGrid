from __future__ import annotations

from orchestrator.config import load_config
from orchestrator.runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from orchestrator.sessions.state import OrchestratorSessionState
from orchestrator.workers.claude_worker import ClaudeWorker
from orchestrator.workers.models import WorkerProgressEvent


class ClaudeRunner(BaseRunner):
    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        task = (session.task or session.goal).strip()
        if not task:
            raise RuntimeError("Claude runner received an empty task.")
        worker = ClaudeWorker(load_config())

        async def on_progress(event: WorkerProgressEvent) -> None:
            session.set_active_worker_runtime(worker="claude", session_mode="new", task_id="", profile="", can_interrupt=False)
            session.set_latest_summary(event.message)
            await emit_progress(event.message, None)

        await emit_progress("Starting Claude CLI", 0.12)
        result = await worker.run(task=task, workspace=session.workspace, on_progress=on_progress)
        session.set_active_worker_runtime(worker="claude", session_mode="new", task_id="", profile="", can_interrupt=False)
        if not result.success:
            raise RuntimeError(result.error or result.summary or "Claude CLI failed.")
        return result.output or result.summary or "Claude CLI completed successfully"
