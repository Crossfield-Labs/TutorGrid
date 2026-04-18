from __future__ import annotations

from orchestrator.workers.base import Worker


class CodexWorker(Worker):
    @property
    def name(self) -> str:
        return "codex"

    async def run(self, task: str, workspace: str) -> str:
        return f"Codex worker placeholder for task: {task}"
