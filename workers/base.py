from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from workers.models import WorkerControlRef, WorkerProgressEvent, WorkerResult

WorkerProgressCallback = Callable[[WorkerProgressEvent], Awaitable[None]]
WorkerControlCallback = Callable[[WorkerControlRef | None], Awaitable[None]]


class Worker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        task: str,
        workspace: str,
        on_progress: WorkerProgressCallback | None = None,
        session_id: str | None = None,
        session_mode: str = "new",
        session_key: str = "primary",
        profile: str | None = None,
        on_control: WorkerControlCallback | None = None,
    ) -> WorkerResult:
        raise NotImplementedError

