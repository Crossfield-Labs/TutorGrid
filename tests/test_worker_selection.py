from __future__ import annotations

import unittest

from backend.config import LangSmithConfig, MemoryConfig, OrchestratorConfig, PlannerConfig, PushConfig
from backend.workers.registry import WorkerRegistry
from backend.workers.selection import select_worker


class WorkerSelectionTests(unittest.TestCase):
    def test_registry_never_registers_claude_even_if_config_requests_it(self) -> None:
        config = OrchestratorConfig(
            planner=PlannerConfig(),
            memory=MemoryConfig(),
            push=PushConfig(),
            langsmith=LangSmithConfig(),
            claude_sdk_enabled=True,
            enabled_workers=["codex", "claude", "opencode"],
        )

        registry = WorkerRegistry(config)

        self.assertEqual(registry.list_names(), ["codex", "opencode"])

    def test_selection_ignores_claude_and_uses_codex_or_opencode(self) -> None:
        selection = select_worker(
            task="Please write documentation and mention Claude nowhere.",
            available_workers=["claude", "codex", "opencode"],
        )

        self.assertIn(selection.worker, {"codex", "opencode"})
        self.assertNotIn("claude", selection.fallback_order)

    def test_explicit_claude_request_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            select_worker(
                task="Use Claude for this task.",
                preferred_worker="claude",
                available_workers=["claude", "codex", "opencode"],
            )


if __name__ == "__main__":
    unittest.main()
