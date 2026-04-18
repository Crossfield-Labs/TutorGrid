from __future__ import annotations

from orchestrator.runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from orchestrator.runtime.runtime import OrchestratorRuntime
from orchestrator.sessions.state import OrchestratorSessionState


class SubAgentRunner(BaseRunner):
    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        runtime = OrchestratorRuntime(
            session=session,
            emit_progress=emit_progress,
            await_user=await_user,
        )
        return await runtime.run()
