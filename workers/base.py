from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from workers.models import WorkerProgressEvent, WorkerResult

WorkerProgressCallback = Callable[[WorkerProgressEvent], Awaitable[None]]


class WorkerAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    async def run(
        self,
        *,
        task: str,
        workspace: str,
        on_progress: WorkerProgressCallback | None = None,
    ) -> WorkerResult:
        raise NotImplementedError
