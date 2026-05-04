from __future__ import annotations

import json
from pathlib import Path

from backend.config import OrchestratorConfig
from backend.workers.base import Worker
from backend.workers.common import resolve_command, run_cli_worker
from backend.workers.models import WorkerResult, WorkerSessionRef


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
        workspace_path = Path(workspace or ".").resolve()
        normalized_mode = (session_mode or "new").strip().lower()
        effective_session_id = (session_id or "").strip()

        command: list[str] = [
            executable,
            "run",
            "--format",
            "json",
            "--dir",
            str(workspace_path),
        ]
        if normalized_mode == "resume" and effective_session_id:
            command.extend(["--session", effective_session_id])
        elif normalized_mode == "continue":
            command.append("--continue")
        if self.config.opencode_model.strip():
            command.extend(["--model", self.config.opencode_model.strip()])
        if self.config.opencode_agent.strip():
            command.extend(["--agent", self.config.opencode_agent.strip()])
        command.append(task)

        result = await run_cli_worker(
            worker_name=self.name,
            command=command,
            workspace=str(workspace_path),
            task=task,
            on_progress=on_progress,
        )

        captured_session_id = effective_session_id or _extract_opencode_session_id(result.output)
        if captured_session_id:
            result.session = WorkerSessionRef(
                worker=self.name,
                session_id=captured_session_id,
                session_key=(session_key or "primary").strip() or "primary",
                mode=normalized_mode,
                continued_from=effective_session_id if normalized_mode in {"resume", "continue"} else "",
            )
        return result


def _extract_opencode_session_id(output: str) -> str:
    if not output:
        return ""
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for key in ("sessionID", "session_id", "sessionId"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


