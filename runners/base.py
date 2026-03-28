from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from sessions.session_state import PcSessionState

ProgressCallback = Callable[[str, float | None], Awaitable[None]]
AwaitUserCallback = Callable[[str, str | None], Awaitable[str]]


class BaseRunner(ABC):
    @abstractmethod
    async def run(
        self,
        session: PcSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        raise NotImplementedError
