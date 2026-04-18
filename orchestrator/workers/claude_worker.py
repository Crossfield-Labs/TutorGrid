from __future__ import annotations

from orchestrator.workers.base import Worker


class ClaudeWorker(Worker):
    @property
    def name(self) -> str:
        return "claude"

    async def run(self, task: str, workspace: str) -> str:
        return f"Claude worker placeholder for task: {task}"
