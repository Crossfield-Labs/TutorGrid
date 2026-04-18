from __future__ import annotations

from abc import ABC, abstractmethod


class Worker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def run(self, task: str, workspace: str) -> str:
        raise NotImplementedError
