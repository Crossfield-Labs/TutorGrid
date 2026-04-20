from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from tui.client import TuiWsClient


class TuiState:
    def __init__(self, workspace: str) -> None:
        self.workspace = workspace
        self.active_session_id = ""
        self.awaiting_input = False
        self.last_status = "unknown"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _print_line(text: str) -> None:
    print(f"[{_now()}] {text}")


def _build_req(method: str, params: dict[str, Any], session_id: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "req",
        "id": str(uuid4()),
        "method": method,
        "params": params,
    }
    if session_id:
        payload["sessionId"] = session_id
    return payload


async def _start_new_task(client: TuiWsClient, state: TuiState, task: str) -> None:
    task_id = str(uuid4())
    await client.send(
        {
            "type": "req",
            "id": str(uuid4()),
            "method": "orchestrator.session.start",
            "taskId": task_id,
            "nodeId": "tui",
            "params": {
                "runner": "pc_subagent",
                "workspace": state.workspace,
                "task": task,
                "goal": task,
            },
        }
    )
    _print_line(f"start -> {task}")


async def _send_input(client: TuiWsClient, state: TuiState, text: str) -> None:
    if not state.active_session_id:
        await _start_new_task(client, state, text)
        return
    intent = "reply" if state.awaiting_input else "instruction"
    await client.send(
        _build_req(
            "orchestrator.session.input",
            {
                "text": text,
                "inputIntent": intent,
            },
            session_id=state.active_session_id,
        )
    )
    _print_line(f"input({intent}) -> {text}")


async def _request_snapshot(client: TuiWsClient, state: TuiState) -> None:
    if not state.active_session_id:
        _print_line("no active session")
        return
    await client.send(
        _build_req(
            "orchestrator.session.snapshot",
            {},
            session_id=state.active_session_id,
        )
    )
    _print_line("snapshot requested")


async def _request_explain(client: TuiWsClient, state: TuiState) -> None:
    if not state.active_session_id:
        _print_line("no active session")
        return
    await client.send(
        _build_req(
            "orchestrator.session.input",
            {"text": "", "inputIntent": "explain"},
            session_id=state.active_session_id,
        )
    )
    _print_line("explain requested")


async def _handle_event(message: dict[str, Any], state: TuiState) -> None:
    if message.get("type") != "event":
        return

    event = str(message.get("event") or "")
    session_id = str(message.get("sessionId") or "")
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}

    if session_id:
        state.active_session_id = session_id

    snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
    if isinstance(snapshot, dict):
        state.awaiting_input = bool(snapshot.get("awaitingInput"))
        status = snapshot.get("status")
        if isinstance(status, str):
            state.last_status = status

    if event.endswith(".summary") and isinstance(payload, dict):
        msg = payload.get("message")
        if isinstance(msg, str) and msg.strip():
            _print_line(f"summary -> {msg}")
            return

    if event.endswith(".await_user"):
        _print_line("awaiting input")
        return

    if event.endswith(".completed"):
        _print_line("completed")
        return

    if event.endswith(".failed"):
        err = payload.get("error") if isinstance(payload, dict) else ""
        _print_line(f"failed -> {err}")
        return

    if event.endswith(".phase") and isinstance(payload, dict):
        phase = payload.get("phase") or (snapshot.get("phase") if isinstance(snapshot, dict) else "")
        _print_line(f"phase -> {phase}")
        return

    _print_line(event)


async def _input_loop(client: TuiWsClient, state: TuiState, stop_event: asyncio.Event) -> None:
    _print_line("commands: /new <task>, /snapshot, /explain, /quit")
    while not stop_event.is_set():
        try:
            line = await asyncio.to_thread(input, "> ")
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break
        text = line.strip()
        if not text:
            continue
        if text in {"/quit", "/exit"}:
            stop_event.set()
            break
        if text.startswith("/new "):
            await _start_new_task(client, state, text.removeprefix("/new ").strip())
            continue
        if text == "/snapshot":
            await _request_snapshot(client, state)
            continue
        if text == "/explain":
            await _request_explain(client, state)
            continue
        await _send_input(client, state, text)


async def run_tui(ws_url: str, token: str, workspace: str) -> None:
    state = TuiState(workspace=workspace)
    client = TuiWsClient(url=ws_url, token=token)
    stop_event = asyncio.Event()
    await client.connect()
    _print_line(f"connected -> {ws_url}")

    async def on_event(message: dict[str, Any]) -> None:
        await _handle_event(message, state)

    receiver = asyncio.create_task(client.receive_loop(on_event))
    sender = asyncio.create_task(_input_loop(client, state, stop_event))

    await stop_event.wait()
    sender.cancel()
    receiver.cancel()
    await client.close()
    _print_line("bye")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PC Orchestrator TUI client")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:3210/ws/orchestrator")
    parser.add_argument("--token", default="")
    parser.add_argument("--workspace", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_tui(ws_url=args.ws_url, token=args.token, workspace=args.workspace))


if __name__ == "__main__":
    main()
