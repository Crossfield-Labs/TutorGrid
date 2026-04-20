from __future__ import annotations

import unittest

from backend.runners.router import RunnerRouter
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


if __name__ == "__main__":
    unittest.main()

