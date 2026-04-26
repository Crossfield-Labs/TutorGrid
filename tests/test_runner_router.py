from __future__ import annotations

import unittest

from backend.runners.router import RunnerRouter
from backend.runners.python_runner import PythonRunner
from backend.runners.shell_runner import ShellRunner
from backend.runners.subagent_runner import SubAgentRunner


class RunnerRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = RunnerRouter()

    def test_subagent_aliases_share_subagent_runner(self) -> None:
        self.assertIsInstance(self.router.get("pc_subagent"), SubAgentRunner)
        self.assertIsInstance(self.router.get("orchestrator"), SubAgentRunner)
        self.assertIsInstance(self.router.get("subagent"), SubAgentRunner)

    def test_unknown_runner_falls_back_to_shell(self) -> None:
        self.assertIsInstance(self.router.get("unknown-runner"), ShellRunner)

    def test_python_runner_aliases_resolve(self) -> None:
        self.assertIsInstance(self.router.get("python"), PythonRunner)
        self.assertIsInstance(self.router.get("python_runner"), PythonRunner)

    def test_claude_runner_is_not_exposed(self) -> None:
        self.assertIsInstance(self.router.get("claude_cli"), ShellRunner)


if __name__ == "__main__":
    unittest.main()

