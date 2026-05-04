from __future__ import annotations

from backend.runners.base import (
    AwaitUserCallback,
    BaseRunner,
    DocWriteCallback,
    MessageEventCallback,
    ProgressCallback,
    SubstepCallback,
)
from backend.runtime.runtime import OrchestratorRuntime
from backend.sessions.state import OrchestratorSessionState


class SubAgentRunner(BaseRunner):
    def __init__(self) -> None:
        self._emit_substep: SubstepCallback | None = None
        self._emit_message_event: MessageEventCallback | None = None
        self._emit_doc_write: DocWriteCallback | None = None

    def set_event_callbacks(
        self,
        *,
        emit_substep: SubstepCallback | None = None,
        emit_message_event: MessageEventCallback | None = None,
        emit_doc_write: DocWriteCallback | None = None,
    ) -> None:
        self._emit_substep = emit_substep
        self._emit_message_event = emit_message_event
        self._emit_doc_write = emit_doc_write

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
            emit_message_event=self._emit_message_event,
            emit_doc_write=self._emit_doc_write,
        )
        return await runtime.run()


