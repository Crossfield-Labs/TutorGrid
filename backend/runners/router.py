from __future__ import annotations

from backend.runners.base import BaseRunner
from backend.runners.claude_runner import ClaudeRunner
from backend.runners.codex_runner import CodexRunner
from backend.runners.opencode_runner import OpencodeRunner
from backend.runners.python_runner import PythonRunner
from backend.runners.shell_runner import ShellRunner
from backend.runners.subagent_runner import SubAgentRunner


class RunnerRouter:
    def __init__(self) -> None:
        self._runners: dict[str, BaseRunner] = {
            "shell": ShellRunner(),
            "python": PythonRunner(),
            "python_runner": PythonRunner(),
            "claude_cli": ClaudeRunner(),
            "codex_cli": CodexRunner(),
            "opencode_cli": OpencodeRunner(),
            "pc_subagent": SubAgentRunner(),
            "orchestrator": SubAgentRunner(),
            "subagent": SubAgentRunner(),
        }

    def get(self, runner_name: str) -> BaseRunner:
        return self._runners.get(runner_name, self._runners["shell"])


