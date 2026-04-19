from __future__ import annotations

from pathlib import Path

from config import OrchestratorConfig
from workers.base import Worker
from workers.common import resolve_command, run_cli_worker
from workers.models import WorkerResult, WorkerSessionRef


class CodexWorker(Worker):
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "codex"

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
        executable = resolve_command(self.config.codex_command)
        workspace_path = Path(workspace or ".").resolve()
        command = [executable]
        if self.config.codex_model.strip():
            command.extend(["-m", self.config.codex_model.strip()])
        normalized_mode = (session_mode or "new").strip().lower()
        effective_session_id = (session_id or "").strip()
        if normalized_mode == "resume" and effective_session_id:
            command.extend(["exec", "resume", effective_session_id, "--skip-git-repo-check", task])
        else:
            command.extend(
                [
                    "-a",
                    "never",
                    "-s",
                    "workspace-write",
                    "-C",
                    str(workspace_path),
                    "exec",
                    "--skip-git-repo-check",
                    task,
                ]
            )
        result = await run_cli_worker(
            worker_name=self.name,
            command=command,
            workspace=str(workspace_path),
            task=task,
            on_progress=on_progress,
        )
        if effective_session_id:
            result.session = WorkerSessionRef(
                worker=self.name,
                session_id=effective_session_id,
                session_key=session_key,
                mode=normalized_mode,
                continued_from=effective_session_id if normalized_mode == "resume" else "",
            )
        return result

