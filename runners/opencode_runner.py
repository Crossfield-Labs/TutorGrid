from __future__ import annotations

from config import load_config
from runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from sessions.state import OrchestratorSessionState
from workers.models import WorkerProgressEvent
from workers.opencode_worker import OpencodeWorker


class OpencodeRunner(BaseRunner):
    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        task = (session.task or session.goal).strip()
        if not task:
            raise RuntimeError("OpenCode runner received an empty task.")
        worker = OpencodeWorker(load_config())

        async def on_progress(event: WorkerProgressEvent) -> None:
            session.set_active_worker_runtime(worker="opencode", session_mode="new", task_id="", profile="", can_interrupt=False)
            session.set_latest_summary(event.message)
            await emit_progress(event.message, None)

        await emit_progress("Starting OpenCode CLI", 0.12)
        result = await worker.run(task=task, workspace=session.workspace, on_progress=on_progress)
        session.set_active_worker_runtime(worker="opencode", session_mode="new", task_id="", profile="", can_interrupt=False)
        if not result.success:
            raise RuntimeError(result.error or result.summary or "OpenCode CLI failed.")
        return result.output or result.summary or "OpenCode CLI completed successfully"

