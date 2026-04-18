from __future__ import annotations

from orchestrator.workers.base import Worker


class OpencodeWorker(Worker):
    @property
    def name(self) -> str:
        return "opencode"

    async def run(self, task: str, workspace: str) -> str:
        return f"OpenCode worker placeholder for task: {task}"
