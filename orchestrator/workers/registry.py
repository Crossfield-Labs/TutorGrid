from __future__ import annotations

from orchestrator.workers.claude_worker import ClaudeWorker
from orchestrator.workers.codex_worker import CodexWorker
from orchestrator.workers.opencode_worker import OpencodeWorker


class WorkerRegistry:
    def __init__(self) -> None:
        self._workers = {
            "codex": CodexWorker(),
            "claude": ClaudeWorker(),
            "opencode": OpencodeWorker(),
        }

    def get(self, name: str):
        return self._workers[name]
