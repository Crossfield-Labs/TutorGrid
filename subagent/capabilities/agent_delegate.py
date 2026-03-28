from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from subagent.tool_base import SubAgentTool
from workers.models import WorkerProgressEvent, WorkerResult
from workers.registry import WorkerRegistry
from workers.selection import select_worker

ProgressFn = Callable[[WorkerProgressEvent], Awaitable[None]]
ResultFn = Callable[[WorkerResult], Awaitable[None]]


class DelegateAgentTool(SubAgentTool):
    def __init__(
        self,
        workspace: str,
        workers: WorkerRegistry,
        on_progress: ProgressFn | None = None,
        on_result: ResultFn | None = None,
    ) -> None:
        self.workspace = Path(workspace or ".").resolve()
        self.workers = workers
        self.on_progress = on_progress
        self.on_result = on_result

    @property
    def name(self) -> str:
        return "delegate_agent"

    @property
    def description(self) -> str:
        return (
            "Delegate a focused coding or code-analysis task to a stronger external CLI backend. "
            "Use worker='opencode' for concrete implementation/editing, worker='codex' for review "
            "or analysis, or omit worker to let the system choose."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task to delegate to the selected coding backend."},
                "worker": {
                    "type": "string",
                    "description": "Optional preferred backend, such as 'opencode' or 'codex'.",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str, worker: str | None = None, **kwargs: Any) -> str:
        selection = select_worker(
            task=task,
            available_workers=self.workers.list_names(),
            preferred_worker=worker,
        )
        if self.on_progress:
            await self.on_progress(
                WorkerProgressEvent(
                    phase="worker_selection",
                    message=f"Selected worker {selection.worker}: {selection.reason}",
                    raw_type="selection",
                    metadata={"selected_worker": selection.worker, "fallback_order": selection.fallback_order},
                )
            )

        attempts = [selection.worker, *selection.fallback_order]
        previous_error = ""
        last_result: WorkerResult | None = None
        for index, candidate in enumerate(attempts):
            candidate_task = task
            if index > 0 and previous_error:
                candidate_task = (
                    f"{task}\n\n"
                    f"Previous backend '{attempts[index - 1]}' failed or was unsuitable with this error:\n"
                    f"{previous_error}\n\n"
                    "Please continue the original task and finish it."
                )
                if self.on_progress:
                    await self.on_progress(
                        WorkerProgressEvent(
                            phase="worker_reroute",
                            message=f"Rerouting from {attempts[index - 1]} to {candidate}",
                            raw_type="reroute",
                            metadata={"from": attempts[index - 1], "to": candidate},
                        )
                    )

            backend = self.workers.get(candidate)
            try:
                result = await backend.run(
                    task=candidate_task,
                    workspace=str(self.workspace),
                    on_progress=self.on_progress,
                )
            except Exception as error:
                result = WorkerResult(
                    worker=candidate,
                    success=False,
                    summary=f"{candidate} failed before producing a result.",
                    output="",
                    error=f"{error.__class__.__name__}: {error}",
                )

            if self.on_result:
                await self.on_result(result)

            last_result = result
            if result.success:
                return result.to_json()

            previous_error = result.error or result.summary or f"{candidate} failed."

        if last_result is None:
            raise RuntimeError("No worker attempts were executed.")
        return last_result.to_json()
