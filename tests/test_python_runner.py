from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.config import LangSmithConfig, MemoryConfig, OrchestratorConfig, PlannerConfig, PushConfig
from backend.runners.python_runner import PythonRunner
from backend.sessions.state import OrchestratorSessionState
from tests.temp_paths import workspace_temp_dir


class _FakeProcess:
    def __init__(self, *, stdout: bytes, stderr: bytes, returncode: int = 0) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return (self._stdout, self._stderr)

    def kill(self) -> None:
        return None


class PythonRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_executes_fenced_python_with_output_truncation(self) -> None:
        runner = PythonRunner()
        with workspace_temp_dir("python-runner-") as temp_dir:
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="python",
                workspace=temp_dir,
                task="请执行这段代码\n```python\nprint('x' * 400)\n```",
                goal="",
            )
            progress_messages: list[str] = []

            async def emit_progress(message: str, _progress: float | None) -> None:
                progress_messages.append(message)

            async def await_user(_prompt: str, _mode: str | None) -> str:
                return ""

            config = OrchestratorConfig(
                planner=PlannerConfig(),
                memory=MemoryConfig(),
                push=PushConfig(),
                langsmith=LangSmithConfig(),
                python_command=sys.executable,
                python_runner_timeout_seconds=10,
                python_runner_output_limit_bytes=128,
                python_runner_allowed_env=["PATH"],
            )

            with (
                patch("backend.runners.python_runner.load_config", return_value=config),
                patch(
                    "backend.runners.python_runner.asyncio.create_subprocess_exec",
                    return_value=_FakeProcess(stdout=("x" * 400).encode("utf-8"), stderr=b""),
                ),
            ):
                output = await runner.run(session, emit_progress, await_user)

        self.assertIn("...[output truncated]", output)
        self.assertTrue(any("Running isolated Python task" in item for item in progress_messages))

    async def test_runner_rejects_workspace_outside_configured_root(self) -> None:
        runner = PythonRunner()
        with workspace_temp_dir("python-root-") as allowed_root, workspace_temp_dir("python-outside-") as outside_root:
            session = OrchestratorSessionState(
                task_id="task-2",
                node_id="node-2",
                runner="python",
                workspace=outside_root,
                task="```python\nprint('hi')\n```",
                goal="",
            )

            async def emit_progress(_message: str, _progress: float | None) -> None:
                return None

            async def await_user(_prompt: str, _mode: str | None) -> str:
                return ""

            config = OrchestratorConfig(
                planner=PlannerConfig(),
                memory=MemoryConfig(),
                push=PushConfig(),
                langsmith=LangSmithConfig(),
                python_command=sys.executable,
                python_runner_workspace_root=str(allowed_root),
            )

            with patch("backend.runners.python_runner.load_config", return_value=config):
                with self.assertRaisesRegex(RuntimeError, "workspace must stay within configured root"):
                    await runner.run(session, emit_progress, await_user)

    async def test_runner_uses_context_python_code_when_present(self) -> None:
        runner = PythonRunner()
        with workspace_temp_dir("python-context-") as temp_dir:
            session = OrchestratorSessionState(
                task_id="task-3",
                node_id="node-3",
                runner="python",
                workspace=temp_dir,
                task="ignore task body",
                goal="",
                context={"python_code": "from pathlib import Path\nprint(Path.cwd().name)"},
            )

            async def emit_progress(_message: str, _progress: float | None) -> None:
                return None

            async def await_user(_prompt: str, _mode: str | None) -> str:
                return ""

            config = OrchestratorConfig(
                planner=PlannerConfig(),
                memory=MemoryConfig(),
                push=PushConfig(),
                langsmith=LangSmithConfig(),
                python_command=sys.executable,
            )

            with (
                patch("backend.runners.python_runner.load_config", return_value=config),
                patch(
                    "backend.runners.python_runner.asyncio.create_subprocess_exec",
                    return_value=_FakeProcess(stdout=Path(temp_dir).name.encode("utf-8"), stderr=b""),
                ),
            ):
                output = await runner.run(session, emit_progress, await_user)

        self.assertEqual(output.strip(), Path(temp_dir).name)

    async def test_python_runner_records_stdout_and_artifacts(self) -> None:
        with workspace_temp_dir("python-artifacts-") as workspace:
            session = OrchestratorSessionState(
                task_id="python-task",
                node_id="python-node",
                runner="python",
                workspace=str(workspace),
                task="run python code",
                goal="run python code",
            )
            session.context["python_code"] = (
                "from pathlib import Path\n"
                "Path('plot.txt').write_text('artifact generated', encoding='utf-8')\n"
                "print('R2=0.94')\n"
            )

            runner = PythonRunner()

            async def emit_progress(message: str, progress: float | None = None) -> None:
                _ = (message, progress)

            async def await_user(message: str, input_mode: str | None = None) -> str:
                _ = (message, input_mode)
                return ""

            result = await runner.run(session, emit_progress, await_user)

        self.assertIn("R2=0.94", result)
        self.assertIn("plot.txt", session.artifacts)
        self.assertTrue(session.worker_runs)
        latest_run = session.worker_runs[-1]
        self.assertEqual(latest_run["worker"], "python_runner")
        self.assertTrue(latest_run["success"])
        artifact_paths = [artifact["path"] for artifact in latest_run["artifacts"]]
        self.assertIn("plot.txt", artifact_paths)


if __name__ == "__main__":
    unittest.main()
