from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sessions.session_state import PcSessionState
from subagent.runtime import PcSubAgentRuntime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PC sub-agent standalone for local testing.")
    parser.add_argument("task", help="Task for the sub-agent to execute")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--goal", default="")
    return parser.parse_args()


async def main_async() -> None:
    args = parse_args()
    session = PcSessionState(
        task_id="dev-cli",
        node_id="dev-cli",
        runner="pc_subagent",
        workspace=args.workspace,
        task=args.task,
        goal=args.goal or args.task,
    )

    async def emit_progress(message: str, progress: float | None = None) -> None:
        prefix = f"[{progress:.2f}] " if progress is not None else ""
        print(prefix + message)

    async def await_user(message: str, input_mode: str | None = None) -> str:
        print(f"[await_user/{input_mode or 'text'}] {message}")
        return input("> ").strip()

    async def emit_substep(kind: str, title: str, status: str, detail: str | None = None) -> None:
        suffix = f" :: {detail}" if detail else ""
        print(f"[substep] {kind} | {title} | {status}{suffix}")

    runtime = PcSubAgentRuntime(
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
