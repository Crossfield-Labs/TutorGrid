from __future__ import annotations

from typing import Awaitable, Callable

from runners.base import BaseRunner
from sessions.session_state import PcSessionState
from subagent.runtime import PcSubAgentRuntime

ProgressCallback = Callable[[str, float | None], Awaitable[None]]
AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]
SubstepCallback = Callable[[str, str, str, str | None], Awaitable[None]]


class PcSubAgentRunner(BaseRunner):
    def __init__(self) -> None:
        self._emit_substep: SubstepCallback | None = None

    def set_event_callbacks(self, *, emit_substep: SubstepCallback | None = None) -> None:
        self._emit_substep = emit_substep

    async def run(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        runtime = PcSubAgentRuntime(
            session=session,
            emit_progress=emit_progress,
            await_user=await_user,
            emit_substep=self._emit_substep,
        )
        return await runtime.run()
