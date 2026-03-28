from __future__ import annotations

from runners.base import BaseRunner
from runners.claude_runner import ClaudeRunner
from runners.codex_runner import CodexRunner
from runners.pc_subagent_runner import PcSubAgentRunner
from runners.shell_runner import ShellRunner


class RunnerRouter:
    def __init__(self) -> None:
        self._runners: dict[str, BaseRunner] = {
            "shell": ShellRunner(),
            "claude_cli": ClaudeRunner(),
            "codex_cli": CodexRunner(),
            "pc_subagent": PcSubAgentRunner(),
        }

    def get(self, runner_name: str) -> BaseRunner:
        return self._runners.get(runner_name, self._runners["shell"])
