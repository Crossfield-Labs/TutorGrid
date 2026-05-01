from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.config import LangSmithConfig, MemoryConfig, OrchestratorConfig, PlannerConfig, PushConfig
from backend.workers.codex_worker import CodexWorker
from backend.workers.models import WorkerResult


def _build_config(*, codex_mcp_config: str = "") -> OrchestratorConfig:
    return OrchestratorConfig(
        planner=PlannerConfig(),
        memory=MemoryConfig(),
        push=PushConfig(),
        langsmith=LangSmithConfig(),
        codex_mcp_config=codex_mcp_config,
    )


class CodexWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_injects_mcp_config_and_redacts_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mcp_config_path = Path(temp_dir) / "mcp.json"
            mcp_config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "filesystem": {
                                "command": "python",
                                "args": ["-m", "server"],
                                "env": {"OPENAI_API_KEY": "demo-key"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            worker = CodexWorker(_build_config(codex_mcp_config=str(mcp_config_path)))
            observed_progress = []
            captured_command: list[str] = []

            async def collect_progress(event):
                observed_progress.append(event)

            async def fake_run_cli_worker(**kwargs):
                nonlocal captured_command
                captured_command = list(kwargs["command"])
                return WorkerResult(
                    worker="codex",
                    success=True,
                    summary="ok",
                    output="done",
                    metadata={"command": list(kwargs["command"])},
                )

            with (
                patch("backend.workers.codex_worker.resolve_command", return_value="codex"),
                patch("backend.workers.codex_worker.run_cli_worker", side_effect=fake_run_cli_worker),
                patch.object(
                    CodexWorker,
                    "_query_mcp_status",
                    AsyncMock(return_value=([{"name": "filesystem", "enabled": True}], "")),
                ),
            ):
                result = await worker.run(
                    task="echo test",
                    workspace=temp_dir,
                    on_progress=collect_progress,
                )

            command_text = " ".join(str(item) for item in captured_command)
            self.assertIn('mcp_servers.filesystem.command="python"', command_text)
            self.assertIn('mcp_servers.filesystem.args=["-m", "server"]', command_text)
            self.assertIn('mcp_servers.filesystem.env.OPENAI_API_KEY="demo-key"', command_text)

            self.assertIn("mcp_status_summary", result.metadata)
            self.assertIn("filesystem", result.metadata["mcp_status_summary"])
            self.assertIn("mcp_servers", result.metadata)

            metadata_command = " ".join(str(item) for item in result.metadata.get("command", []))
            self.assertNotIn("demo-key", metadata_command)
            self.assertIn("mcp_servers.filesystem.env.OPENAI_API_KEY=***", metadata_command)
            self.assertTrue(any(event.metadata.get("mcp_status_summary") for event in observed_progress))

    async def test_missing_mcp_config_emits_status_summary_without_crashing(self) -> None:
        worker = CodexWorker(_build_config(codex_mcp_config="Z:/not-exists/mcp.json"))
        captured_command: list[str] = []

        async def fake_run_cli_worker(**kwargs):
            nonlocal captured_command
            captured_command = list(kwargs["command"])
            return WorkerResult(
                worker="codex",
                success=True,
                summary="ok",
                output="done",
                metadata={"command": list(kwargs["command"])},
            )

        with (
            patch("backend.workers.codex_worker.resolve_command", return_value="codex"),
            patch("backend.workers.codex_worker.run_cli_worker", side_effect=fake_run_cli_worker),
            patch.object(CodexWorker, "_query_mcp_status", AsyncMock(return_value=([], ""))),
        ):
            result = await worker.run(task="echo test", workspace=".")

        command_text = " ".join(str(item) for item in captured_command)
        self.assertNotIn("mcp_servers.", command_text)
        self.assertIn("mcp_status_summary", result.metadata)
        self.assertIn("MCP config file not found", result.metadata["mcp_status_summary"])


if __name__ == "__main__":
    unittest.main()
