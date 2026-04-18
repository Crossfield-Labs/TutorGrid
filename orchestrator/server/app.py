from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from orchestrator.runners.router import RunnerRouter
from orchestrator.server.protocol import OrchestratorRequest, build_event
from orchestrator.sessions.manager import SessionManager
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


ROOT = Path(__file__).resolve().parents[1]
session_manager = SessionManager()
runner_router = RunnerRouter()
session_waiters: dict[str, asyncio.Future[str]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orchestrator standalone server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3210)
    return parser.parse_args()


async def send_event(
    websocket: WebSocketServerProtocol,
    *,
    event: str,
    task_id: str | None,
    node_id: str | None,
    session_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    await websocket.send(
        json.dumps(
            build_event(
                event=event,
                task_id=task_id,
                node_id=node_id,
                session_id=session_id,
                payload=payload,
            ),
            ensure_ascii=False,
        )
    )


async def _await_user(session_id: str, message: str, input_mode: str = "text") -> str:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    session_waiters[session_id] = future
    return await future


async def _run_session(session_id: str, websocket: WebSocketServerProtocol) -> None:
    session = session_manager.get(session_id)
    if session is None:
        return
    runner = runner_router.get(session.runner)

    async def emit_progress(message: str, progress: float | None = None) -> None:
        session.last_progress_message = message
        await send_event(
            websocket,
            event="orchestrator.session.progress",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={"message": message, "progress": progress},
        )

    async def await_user(message: str, input_mode: str | None = None) -> str:
        session.awaiting_input = True
        session.pending_user_prompt = message
        await send_event(
            websocket,
            event="orchestrator.session.await_user",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={"message": message, "inputMode": input_mode or "text"},
        )
        reply = await _await_user(session.session_id, message, input_mode or "text")
        session.awaiting_input = False
        session.pending_user_prompt = ""
        return reply

    result = await runner.run(session, emit_progress, await_user)
    session.result = result
    session.status = "COMPLETED"
    await send_event(
        websocket,
        event="orchestrator.session.completed",
        task_id=session.task_id,
        node_id=session.node_id,
        session_id=session.session_id,
        payload={"result": result},
    )


async def websocket_handler(websocket: WebSocketServerProtocol, path: str) -> None:
    if path != "/ws/orchestrator":
        await websocket.close(code=1008, reason="Unsupported path")
        return

    try:
        async for raw_message in websocket:
            payload = json.loads(raw_message)
            request = OrchestratorRequest.from_dict(payload)

            if request.method == "orchestrator.session.start":
                session = session_manager.create(
                    task_id=request.task_id or "task",
                    node_id=request.node_id or "node",
                    runner=request.params.runner,
                    workspace=request.params.workspace or str(ROOT),
                    task=request.params.task,
                    goal=request.params.goal,
                )
                await send_event(
                    websocket,
                    event="orchestrator.session.started",
                    task_id=session.task_id,
                    node_id=session.node_id,
                    session_id=session.session_id,
                    payload={"message": "session started", "runner": session.runner},
                )
                asyncio.create_task(_run_session(session.session_id, websocket))
                continue

            if request.method == "orchestrator.session.input" and request.session_id:
                waiter = session_waiters.get(request.session_id)
                if waiter is not None and not waiter.done():
                    waiter.set_result(request.params.text)
                continue

            await send_event(
                websocket,
                event="orchestrator.session.failed",
                task_id=request.task_id,
                node_id=request.node_id,
                session_id=request.session_id,
                payload={"message": f"Unsupported method: {request.method}"},
            )
    except ConnectionClosed:
        return


async def run_server(host: str, port: int) -> None:
    async with serve(websocket_handler, host, port):
        print(f"Orchestrator listening on ws://{host}:{port}/ws/orchestrator")
        await asyncio.Future()


def main() -> None:
    args = parse_args()
    asyncio.run(run_server(args.host, args.port))
