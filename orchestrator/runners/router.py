from __future__ import annotations

from orchestrator.runners.base import BaseRunner
from orchestrator.runners.claude_runner import ClaudeRunner
from orchestrator.runners.codex_runner import CodexRunner
from orchestrator.runners.opencode_runner import OpencodeRunner
from orchestrator.runners.shell_runner import ShellRunner
from orchestrator.runners.subagent_runner import SubAgentRunner


class RunnerRouter:
    def __init__(self) -> None:
        self._runners: dict[str, BaseRunner] = {
            "shell": ShellRunner(),
            "claude_cli": ClaudeRunner(),
            "codex_cli": CodexRunner(),
            "opencode_cli": OpencodeRunner(),
            "pc_subagent": SubAgentRunner(),
            "orchestrator": SubAgentRunner(),
            "subagent": SubAgentRunner(),
        }

    def get(self, runner_name: str) -> BaseRunner:
        return self._runners.get(runner_name, self._runners["shell"])
