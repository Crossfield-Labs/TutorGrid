from __future__ import annotations

from runners.base import BaseRunner
from runners.claude_runner import ClaudeRunner
from runners.codex_runner import CodexRunner
from runners.opencode_runner import OpencodeRunner
from runners.shell_runner import ShellRunner
from runners.subagent_runner import SubAgentRunner


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

