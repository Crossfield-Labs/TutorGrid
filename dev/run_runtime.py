from __future__ import annotations

import argparse
import asyncio

from runtime.runtime import OrchestratorRuntime
from sessions.state import OrchestratorSessionState


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the standalone orchestrator runtime.")
    parser.add_argument("task")
    parser.add_argument("--workspace", default=".")
    return parser.parse_args()


async def main_async() -> None:
    args = parse_args()
    session = OrchestratorSessionState(
        task_id="dev-task",
        node_id="dev-node",
        runner="orchestrator",
        workspace=args.workspace,
        task=args.task,
        goal=args.task,
    )

    async def emit_progress(message: str, progress: float | None = None) -> None:
        prefix = f"[{progress:.2f}] " if progress is not None else ""
        print(prefix + message)

    async def emit_substep(kind: str, title: str, status: str, detail: str | None = None) -> None:
        suffix = f" :: {detail}" if detail else ""
        print(f"[substep] {kind} | {title} | {status}{suffix}")

    async def await_user(message: str, input_mode: str | None = None) -> str:
        print(f"[await_user/{input_mode or 'text'}] {message}")
        return input("> ").strip()

    runtime = OrchestratorRuntime(
        session=session,
        emit_progress=emit_progress,
        await_user=await_user,
        emit_substep=emit_substep,
    )
    result = await runtime.run()
    print("\n=== FINAL RESULT ===")
    print(result)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

