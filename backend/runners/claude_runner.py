from __future__ import annotations

from backend.runners.base import AwaitUserCallback, BaseRunner, ProgressCallback
from backend.sessions.state import OrchestratorSessionState


class ClaudeRunner(BaseRunner):
    async def run(
        self,
        session: OrchestratorSessionState,
        emit_progress: ProgressCallback,
        await_user: AwaitUserCallback,
    ) -> str:
        raise RuntimeError("Claude runner is disabled in this build. Use codex_cli, opencode_cli, or orchestrator.")


