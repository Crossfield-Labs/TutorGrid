from __future__ import annotations

from config.subagent_config import SubAgentConfig
from workers.base import WorkerAdapter
from workers.codex_worker import CodexWorker
from workers.opencode_worker import OpencodeWorker


class WorkerRegistry:
    def __init__(self, config: SubAgentConfig) -> None:
        self._workers: dict[str, WorkerAdapter] = {}
        self.register(OpencodeWorker(config))
        self.register(CodexWorker(config))

    def register(self, worker: WorkerAdapter) -> None:
        self._workers[worker.name] = worker

    def get(self, name: str) -> WorkerAdapter:
        normalized = name.strip().lower()
        worker = self._workers.get(normalized)
        if worker is None:
            raise RuntimeError(f"Worker not found: {name}")
        return worker

    def list_names(self) -> list[str]:
        return sorted(self._workers.keys())
