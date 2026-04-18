from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from orchestrator.sessions.state import OrchestratorSessionState

ProgressCallback = Callable[[str, float | None], Awaitable[None]]
AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]


class BaseRunner(ABC):
    @abstractmethod
    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        raise NotImplementedError
