from __future__ import annotations

from orchestrator.runners.base import AwaitUserCallback, BaseRunner, ProgressCallback, SubstepCallback
from orchestrator.runtime.runtime import OrchestratorRuntime
from orchestrator.sessions.state import OrchestratorSessionState


class SubAgentRunner(BaseRunner):
    def __init__(self) -> None:
        self._emit_substep: SubstepCallback | None = None

    def set_event_callbacks(self, *, emit_substep: SubstepCallback | None = None) -> None:
        self._emit_substep = emit_substep

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
            emit_substep=self._emit_substep,
        )
        return await runtime.run()
