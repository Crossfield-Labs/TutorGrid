from __future__ import annotations

from orchestrator.runners.base import BaseRunner
from orchestrator.runners.subagent_runner import SubAgentRunner


class RunnerRouter:
    def __init__(self) -> None:
        self._runners: dict[str, BaseRunner] = {
            "orchestrator": SubAgentRunner(),
            "subagent": SubAgentRunner(),
        }

    def get(self, runner_name: str) -> BaseRunner:
        return self._runners.get(runner_name, self._runners["orchestrator"])
