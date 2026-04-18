from __future__ import annotations

from orchestrator.config import OrchestratorConfig
from orchestrator.workers.claude_worker import ClaudeWorker
from orchestrator.workers.codex_worker import CodexWorker
from orchestrator.workers.opencode_worker import OpencodeWorker


class WorkerRegistry:
    def __init__(self, config: OrchestratorConfig) -> None:
        workers = {"codex": CodexWorker(config), "opencode": OpencodeWorker(config)}
        if config.claude_sdk_enabled:
            workers["claude"] = ClaudeWorker(config)
        enabled = {item.strip().lower() for item in config.enabled_workers if item.strip()}
        self._workers = {name: worker for name, worker in workers.items() if not enabled or name in enabled}

    def get(self, name: str):
        return self._workers[name]

    def list_names(self) -> list[str]:
        return sorted(self._workers.keys())
