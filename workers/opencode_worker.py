from __future__ import annotations

from config import OrchestratorConfig
from workers.base import Worker
from workers.common import resolve_command, run_cli_worker
from workers.models import WorkerResult


class OpencodeWorker(Worker):
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "opencode"

    async def run(
        self,
        task: str,
        workspace: str,
        on_progress=None,
        session_id: str | None = None,
        session_mode: str = "new",
        session_key: str = "primary",
        profile: str | None = None,
        on_control=None,
    ) -> WorkerResult:
        executable = resolve_command(self.config.opencode_command)
        command = [
            executable,
            "run",
            "--format",
            "json",
            "--dir",
            workspace,
        ]
        if self.config.opencode_model.strip():
            command.extend(["--model", self.config.opencode_model.strip()])
        if self.config.opencode_agent.strip():
            command.extend(["--agent", self.config.opencode_agent.strip()])
        command.append(task)
        return await run_cli_worker(
            worker_name=self.name,
            command=command,
            workspace=workspace,
            task=task,
            on_progress=on_progress,
        )

