from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from orchestrator.runners.router import RunnerRouter
from orchestrator.server.protocol import OrchestratorRequest, build_event
from orchestrator.sessions.manager import SessionManager
from orchestrator.sessions.state import OrchestratorSessionState
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


ROOT = Path(__file__).resolve().parents[1]
session_manager = SessionManager()
runner_router = RunnerRouter()
session_waiters: dict[str, asyncio.Future[str]] = {}
session_tasks: dict[str, asyncio.Task[None]] = {}
session_subscribers: dict[str, set[WebSocketServerProtocol]] = defaultdict(set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orchestrator standalone server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3210)
    parser.add_argument("--token", default="")
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


def _subscribe(session_id: str, websocket: WebSocketServerProtocol) -> None:
    session_subscribers[session_id].add(websocket)


def _unsubscribe(session_id: str, websocket: WebSocketServerProtocol) -> None:
    subscribers = session_subscribers.get(session_id)
    if not subscribers:
        return
    subscribers.discard(websocket)
    if not subscribers:
        session_subscribers.pop(session_id, None)


async def _broadcast_event(
    session: OrchestratorSessionState,
    *,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    stale: list[WebSocketServerProtocol] = []
    for websocket in list(session_subscribers.get(session.session_id, set())):
        try:
            await send_event(
                websocket,
                event=event,
                task_id=session.task_id,
                node_id=session.node_id,
                session_id=session.session_id,
                payload=payload,
            )
        except ConnectionClosed:
            stale.append(websocket)
    for websocket in stale:
        _unsubscribe(session.session_id, websocket)


async def _run_session(session_id: str, websocket: WebSocketServerProtocol) -> None:
    session = session_manager.get(session_id)
    if session is None:
        return
    runner = runner_router.get(session.runner)
    session.phase = "starting"
    session.mark(status="RUNNING", message="Session started")
    session_manager.update(session)
    await _broadcast_event(
        session,
        event="orchestrator.session.started",
        payload={"message": "session started", "runner": session.runner, "snapshot": session.build_snapshot()},
    )

    async def emit_progress(message: str, progress: float | None = None) -> None:
        session.mark(status="RUNNING", message=message)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.progress",
            payload={"message": message, "progress": progress, "snapshot": session.build_snapshot()},
        )

    async def await_user(message: str, input_mode: str | None = None) -> str:
        session.request_user_input(message, input_mode or "text")
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.await_user",
            payload={"message": message, "inputMode": input_mode or "text", "snapshot": session.build_snapshot()},
        )
        reply = await _await_user(session.session_id, message, input_mode or "text")
        session.resume_with_input(reply)
        session_manager.update(session)
        return reply

    try:
        result = await runner.run(session, emit_progress, await_user)
        session.result = result
        session.phase = "completed"
        session.stop_reason = "completed"
        session.mark(status="COMPLETED", message="Session completed")
        session.latest_summary = result[:400] if result else "Session completed"
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.completed",
            payload={"result": result, "snapshot": session.build_snapshot()},
        )
    except asyncio.CancelledError:
        session.error = "Session cancelled"
        session.phase = "cancelled"
        session.stop_reason = "cancelled"
        session.mark(status="CANCELLED", message=session.error)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.failed",
            payload={"error": session.error, "snapshot": session.build_snapshot()},
        )
        raise
    except Exception as exc:
        session.error = str(exc)
        session.phase = "failed"
        session.stop_reason = "failed"
        session.mark(status="FAILED", message=session.error)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.failed",
            payload={"error": session.error, "snapshot": session.build_snapshot()},
        )
    finally:
        session_waiters.pop(session.session_id, None)
        session_tasks.pop(session.session_id, None)


def _is_authorized(websocket: WebSocketServerProtocol, required_token: str) -> bool:
    if not required_token:
        return True
    actual = websocket.request_headers.get("X-MetaAgent-Token", "")
    return actual == required_token


async def websocket_handler(websocket: WebSocketServerProtocol, path: str, required_token: str) -> None:
    if path != "/ws/orchestrator":
        await websocket.close(code=1008, reason="Unsupported path")
        return
    if not _is_authorized(websocket, required_token):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    subscribed_session_ids: set[str] = set()

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
                _subscribe(session.session_id, websocket)
                subscribed_session_ids.add(session.session_id)
                session_task = asyncio.create_task(_run_session(session.session_id, websocket))
                session_tasks[session.session_id] = session_task
                continue

            if request.method == "orchestrator.session.input" and request.session_id:
                session = session_manager.get(request.session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event="orchestrator.session.failed",
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                _subscribe(session.session_id, websocket)
                subscribed_session_ids.add(session.session_id)
                waiter = session_waiters.get(request.session_id)
                if waiter is not None and not waiter.done():
                    waiter.set_result(request.params.text)
                    await _broadcast_event(
                        session,
                        event="orchestrator.session.followup.accepted",
                        payload={
                            "message": "Accepted user reply.",
                            "intent": request.params.input_intent,
                            "text": request.params.text,
                        },
                    )
                elif request.params.input_intent in {"redirect", "comment", "instruction"}:
                    session_manager.enqueue_followup(
                        request.session_id,
                        text=request.params.text,
                        intent=request.params.input_intent,
                        target=request.params.target,
                    )
                    await _broadcast_event(
                        session,
                        event="orchestrator.session.followup.accepted",
                        payload={
                            "message": "Accepted follow-up for the current session.",
                            "intent": request.params.input_intent,
                            "text": request.params.text,
                            "target": request.params.target,
                            "snapshot": session.build_snapshot(),
                        },
                    )
                continue

            if request.method == "orchestrator.session.snapshot" and request.session_id:
                session = session_manager.get(request.session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event="orchestrator.session.failed",
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                _subscribe(session.session_id, websocket)
                subscribed_session_ids.add(session.session_id)
                await send_event(
                    websocket,
                    event="orchestrator.session.snapshot",
                    task_id=session.task_id,
                    node_id=session.node_id,
                    session_id=session.session_id,
                    payload={"snapshot": session.build_snapshot(), "message": session.latest_summary or session.last_progress_message},
                )
                continue

            if request.method == "orchestrator.session.cancel" and request.session_id:
                task = session_tasks.get(request.session_id)
                if task is not None:
                    task.cancel()
                continue

            if request.method == "orchestrator.session.interrupt" and request.session_id:
                session = session_manager.get(request.session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event="orchestrator.session.failed",
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                session.stop_reason = "interrupt_requested"
                session.latest_summary = request.params.text or "Interrupt requested."
                session_manager.update(session)
                await _broadcast_event(
                    session,
                    event="orchestrator.session.followup.accepted",
                    payload={"message": session.latest_summary, "intent": "interrupt", "snapshot": session.build_snapshot()},
                )
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
    finally:
        for session_id in subscribed_session_ids:
            _unsubscribe(session_id, websocket)


async def run_server(host: str, port: int, token: str) -> None:
    async with serve(lambda ws, path: websocket_handler(ws, path, token), host, port):
        print(f"Orchestrator listening on ws://{host}:{port}/ws/orchestrator")
        await asyncio.Future()


def main() -> None:
    args = parse_args()
    asyncio.run(run_server(args.host, args.port, args.token.strip()))
