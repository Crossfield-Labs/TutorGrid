from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from subagent.tool_base import SubAgentTool
from workers.base import WorkerAdapter
from workers.models import WorkerProgressEvent, WorkerResult

ProgressFn = Callable[[WorkerProgressEvent], Awaitable[None]]
ResultFn = Callable[[WorkerResult], Awaitable[None]]


class DelegateOpenCodeTool(SubAgentTool):
    def __init__(
        self,
        workspace: str,
        worker: WorkerAdapter,
        on_progress: ProgressFn | None = None,
        on_result: ResultFn | None = None,
    ) -> None:
        self.workspace = Path(workspace or ".").resolve()
        self.worker = worker
        self.on_progress = on_progress
        self.on_result = on_result

    @property
    def name(self) -> str:
        return "delegate_opencode"

    @property
    def description(self) -> str:
        return "Delegate a focused coding or analysis task to the local opencode CLI and return the result."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task to delegate to opencode."},
            },
            "required": ["task"],
        }

    async def execute(self, task: str, **kwargs: Any) -> str:
        result = await self.worker.run(
            task=task,
            workspace=str(self.workspace),
            on_progress=self.on_progress,
        )
        if self.on_result:
            await self.on_result(result)
        return result.to_json()
