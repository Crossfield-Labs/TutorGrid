from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from typing import Any

from router.runner_router import RunnerRouter
from server.protocol import PcSessionRequest, build_event
from sessions.session_manager import SessionManager
from sessions.session_state import PcSessionState
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


session_manager = SessionManager()
runner_router = RunnerRouter()
session_waiters: dict[str, asyncio.Future[str]] = {}
session_tasks: dict[str, asyncio.Task[None]] = {}
session_subscribers: dict[str, set[WebSocketServerProtocol]] = defaultdict(set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MetaAgent PC Orchestrator Step 2A")
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


async def _broadcast_event(
    session: PcSessionState,
    *,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    subscribers = list(session_subscribers.get(session.session_id, set()))
    stale: list[WebSocketServerProtocol] = []
    for websocket in subscribers:
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

    if stale:
        for websocket in stale:
            session_subscribers[session.session_id].discard(websocket)


def _build_explanation_message(session: PcSessionState) -> str:
    snapshot = session.build_snapshot()
    lines: list[str] = [
        f"当前 PC 会话状态：{snapshot['status']}，阶段：{snapshot['phase']}。",
    ]
    if snapshot["activeWorker"]:
        worker_line = f"当前 worker：{snapshot['activeWorker']}"
        if snapshot["activeSessionMode"]:
            worker_line += f"（session_mode={snapshot['activeSessionMode']}）"
        lines.append(worker_line + "。")
    if snapshot["latestSummary"]:
        lines.append(f"最近摘要：{snapshot['latestSummary']}")
    elif snapshot["lastProgressMessage"]:
        lines.append(f"最近进展：{snapshot['lastProgressMessage']}")
    if snapshot["awaitingInput"]:
        lines.append(f"当前正在等待你的输入：{snapshot['pendingUserPrompt']}")
    elif snapshot["pendingFollowups"]:
        lines.append(f"当前有 {len(snapshot['pendingFollowups'])} 条 follow-up 已接收，等待下一安全点处理。")
    if snapshot["latestArtifactSummary"]:
        lines.append(f"产物情况：{snapshot['latestArtifactSummary']}")
    if snapshot["artifacts"]:
        lines.append(f"当前已记录产物 {len(snapshot['artifacts'])} 个。")
    return "\n".join(lines)


async def _emit_projection_updates(session: PcSessionState) -> None:
    snapshot = session.build_snapshot()
    previous = session.context.get("_projection_state")
    previous_state = previous if isinstance(previous, dict) else {}

    if previous_state.get("phase") != snapshot["phase"]:
        await _broadcast_event(
            session,
            event="pc.session.phase",
            payload={
                "phase": snapshot["phase"],
                "message": snapshot["latestSummary"] or snapshot["lastProgressMessage"],
                "runner": session.runner,
                "snapshotVersion": snapshot["snapshotVersion"],
            },
        )

    current_worker = {
        "worker": snapshot["activeWorker"],
        "sessionMode": snapshot["activeSessionMode"],
    }
    previous_worker = {
        "worker": previous_state.get("activeWorker", ""),
        "sessionMode": previous_state.get("activeSessionMode", ""),
    }
    if current_worker != previous_worker and snapshot["activeWorker"]:
        await _broadcast_event(
            session,
            event="pc.session.worker",
            payload={
                "worker": snapshot["activeWorker"],
                "sessionMode": snapshot["activeSessionMode"],
                "message": snapshot["latestSummary"] or snapshot["lastProgressMessage"],
                "runner": session.runner,
                "snapshotVersion": snapshot["snapshotVersion"],
            },
        )

    if previous_state.get("latestSummary") != snapshot["latestSummary"] and snapshot["latestSummary"]:
        await _broadcast_event(
            session,
            event="pc.session.summary",
            payload={
                "message": snapshot["latestSummary"],
                "phase": snapshot["phase"],
                "runner": session.runner,
                "snapshotVersion": snapshot["snapshotVersion"],
            },
        )

    if (
        previous_state.get("latestArtifactSummary") != snapshot["latestArtifactSummary"]
        and snapshot["latestArtifactSummary"]
    ):
        await _broadcast_event(
            session,
            event="pc.session.artifact_summary",
            payload={
                "message": snapshot["latestArtifactSummary"],
                "artifacts": snapshot["artifacts"],
                "runner": session.runner,
                "snapshotVersion": snapshot["snapshotVersion"],
            },
        )

    if previous_state.get("snapshotVersion") != snapshot["snapshotVersion"]:
        await _broadcast_event(
            session,
            event="pc.session.snapshot",
            payload={
                "message": snapshot["latestSummary"] or snapshot["lastProgressMessage"],
                "runner": session.runner,
                "snapshot": snapshot,
            },
        )

    session.context["_projection_state"] = {
        "phase": snapshot["phase"],
        "activeWorker": snapshot["activeWorker"],
        "activeSessionMode": snapshot["activeSessionMode"],
        "latestSummary": snapshot["latestSummary"],
        "latestArtifactSummary": snapshot["latestArtifactSummary"],
        "snapshotVersion": snapshot["snapshotVersion"],
    }


async def _emit_progress(session: PcSessionState, message: str, progress: float | None = None) -> None:
    session.mark(status="RUNNING", message=message)
    session_manager.update(session)
    await _broadcast_event(
        session,
        event="pc.session.progress",
        payload={
            "message": message,
            "progress": progress,
            "runner": session.runner,
        },
    )
    await _emit_projection_updates(session)


async def _emit_substep(
    session: PcSessionState,
    *,
    kind: str,
    title: str,
    status: str,
    detail: str | None = None,
) -> None:
    record = {
        "kind": kind,
        "title": title,
        "status": status,
        "detail": detail or "",
    }
    session.substeps.append(record)
    session_manager.update(session)
    await _broadcast_event(
        session,
        event=f"pc.session.subnode.{status}",
        payload={
            "kind": kind,
            "title": title,
            "status": status,
            "message": detail or title,
            "detail": detail or "",
            "runner": session.runner,
        },
    )
    await _emit_projection_updates(session)


async def _await_user(session: PcSessionState, message: str, input_mode: str | None = None) -> str:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    session.request_user_input(message, input_mode or "text")
    session_manager.update(session)
    session_waiters[session.session_id] = future

    await _broadcast_event(
        session,
        event="pc.session.await_user",
        payload={
            "message": message,
            "inputMode": input_mode or "text",
            "runner": session.runner,
        },
    )
    await _emit_projection_updates(session)

    user_input = await future
    session_waiters.pop(session.session_id, None)
    session.resume_with_input(user_input)
    session_manager.update(session)
    await _emit_progress(session, f"User replied: {user_input}", 0.62)
    return user_input


async def _run_session(session: PcSessionState) -> None:
    try:
        session.set_phase("starting")
        session.set_latest_summary("PC session created")
        session.mark(status="RUNNING", message="PC session created")
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="pc.session.started",
            payload={
                "message": f"PC session started with runner {session.runner}",
                "progress": 0.05,
                "runner": session.runner,
            },
        )
        await _emit_projection_updates(session)

        runner = runner_router.get(session.runner)
        async def emit_progress(message: str, progress: float | None = None) -> None:
            await _emit_progress(session, message, progress)

        async def await_user(message: str, input_mode: str | None = None) -> str:
            return await _await_user(session, message, input_mode)

        async def emit_substep(kind: str, title: str, status: str, detail: str | None = None) -> None:
            await _emit_substep(
                session,
                kind=kind,
                title=title,
                status=status,
                detail=detail,
            )

        if hasattr(runner, "set_event_callbacks"):
            runner.set_event_callbacks(emit_substep=emit_substep)

        result = await runner.run(session, emit_progress, await_user)
        session.result = result
        session.set_phase("completed")
        session.set_stop_reason("completed")
        session.set_latest_summary(result[:400] if result else "PC session completed")
        session.mark(status="COMPLETED", message="PC session completed")
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="pc.session.completed",
            payload={
                "message": "PC session completed",
                "result": result,
                "runner": session.runner,
                "progress": 1.0,
                "artifacts": session.artifacts,
                "workerRuns": session.worker_runs,
            },
        )
        await _emit_projection_updates(session)
    except asyncio.CancelledError:
        session.error = "PC session cancelled"
        session.set_phase("cancelled")
        session.set_stop_reason("cancelled")
        session.set_latest_summary(session.error)
        session.mark(status="CANCELLED", message=session.error)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="pc.session.failed",
            payload={
                "message": session.error,
                "error": session.error,
                "runner": session.runner,
            },
        )
        await _emit_projection_updates(session)
        raise
    except Exception as exc:
        session.error = str(exc)
        session.set_phase("failed")
        session.set_stop_reason("failed")
        session.set_latest_summary(session.error)
        session.mark(status="FAILED", message=session.error)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="pc.session.failed",
            payload={
                "message": session.error,
                "error": session.error,
                "runner": session.runner,
            },
        )
        await _emit_projection_updates(session)
    finally:
        session_waiters.pop(session.session_id, None)
        session_tasks.pop(session.session_id, None)


def _subscribe(session_id: str, websocket: WebSocketServerProtocol) -> None:
    session_subscribers[session_id].add(websocket)


def _unsubscribe(session_id: str, websocket: WebSocketServerProtocol) -> None:
    subscribers = session_subscribers.get(session_id)
    if not subscribers:
        return
    subscribers.discard(websocket)
    if not subscribers:
        session_subscribers.pop(session_id, None)


async def handle_start_request(
    websocket: WebSocketServerProtocol,
    request: PcSessionRequest,
) -> str:
    params = request.params
    task_text = params.task.strip() or params.goal.strip()
    session = session_manager.create(
        task_id=request.task_id,
        node_id=request.node_id,
        runner=params.runner.strip() or "shell",
        workspace=params.workspace.strip(),
        task=task_text,
        goal=params.goal.strip(),
    )
    if params.command:
        session.context["command"] = params.command

    _subscribe(session.session_id, websocket)
    session_task = asyncio.create_task(_run_session(session))
    session_tasks[session.session_id] = session_task
    return session.session_id


async def handle_input_request(
    websocket: WebSocketServerProtocol,
    request: PcSessionRequest,
) -> str | None:
    session_id = (request.session_id or "").strip()
    if not session_id:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=None,
            payload={"message": "Missing sessionId", "error": "Missing sessionId"},
        )
        return None

    session = session_manager.get(session_id)
    if session is None:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=session_id,
            payload={"message": "Session not found", "error": "Session not found"},
        )
        return None

    _subscribe(session_id, websocket)
    input_intent = (request.params.input_intent or "reply").strip().lower() or "reply"
    input_text = request.params.text.strip()
    target = request.params.target.strip()
    waiter = session_waiters.get(session_id)

    if input_intent == "explain":
        explanation = _build_explanation_message(session)
        await send_event(
            websocket,
            event="pc.session.summary",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={
                "message": explanation,
                "runner": session.runner,
                "snapshot": session.build_snapshot(),
            },
        )
        return session_id

    if waiter is not None and not waiter.done():
        waiter.set_result(input_text)
        await _broadcast_event(
            session,
            event="pc.session.followup.accepted",
            payload={
                "message": f"Accepted {input_intent or 'reply'} input for the waiting PC session.",
                "intent": input_intent,
                "text": input_text,
                "target": target,
                "runner": session.runner,
            },
        )
        return session_id

    if input_intent == "reply":
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={
                "message": "Session is not waiting for user input",
                "error": "Session is not waiting for user input",
            },
        )
        return session_id

    if not input_text:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={
                "message": "Follow-up text cannot be empty",
                "error": "Follow-up text cannot be empty",
            },
        )
        return session_id

    queued = session_manager.enqueue_followup(
        session_id,
        text=input_text,
        intent=input_intent,
        target=target,
    )
    if queued is None:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=session.task_id,
            node_id=session.node_id,
            session_id=session.session_id,
            payload={
                "message": "Session not found while queueing follow-up",
                "error": "Session not found while queueing follow-up",
            },
        )
        return session_id

    session.set_latest_summary(f"Accepted {input_intent} follow-up: {input_text}".strip())
    session_manager.update(session)
    await _broadcast_event(
        session,
        event="pc.session.followup.accepted",
        payload={
            "message": f"Accepted {input_intent} follow-up for the current PC session.",
            "intent": input_intent,
            "text": input_text,
            "target": target,
            "runner": session.runner,
            "followup": queued["followup"],
        },
    )
    await _emit_projection_updates(session)
    return session_id


async def handle_snapshot_request(
    websocket: WebSocketServerProtocol,
    request: PcSessionRequest,
) -> str | None:
    session_id = (request.session_id or "").strip()
    if not session_id:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=None,
            payload={"message": "Missing sessionId", "error": "Missing sessionId"},
        )
        return None

    session = session_manager.get(session_id)
    if session is None:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=session_id,
            payload={"message": "Session not found", "error": "Session not found"},
        )
        return None

    _subscribe(session_id, websocket)
    await send_event(
        websocket,
        event="pc.session.snapshot",
        task_id=session.task_id,
        node_id=session.node_id,
        session_id=session.session_id,
        payload={
            "message": session.latest_summary or session.last_progress_message,
            "runner": session.runner,
            "snapshot": session.build_snapshot(),
        },
    )
    return session_id


async def handle_cancel_request(
    websocket: WebSocketServerProtocol,
    request: PcSessionRequest,
) -> str | None:
    session_id = (request.session_id or "").strip()
    if not session_id:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=None,
            payload={"message": "Missing sessionId", "error": "Missing sessionId"},
        )
        return None

    session = session_manager.get(session_id)
    if session is None:
        await send_event(
            websocket,
            event="pc.session.failed",
            task_id=request.task_id,
            node_id=request.node_id,
            session_id=session_id,
            payload={"message": "Session not found", "error": "Session not found"},
        )
        return None

    task = session_tasks.get(session_id)
    if task is not None:
        task.cancel()
    return session_id


def _is_authorized(websocket: WebSocketServerProtocol, required_token: str) -> bool:
    if not required_token:
        return True
    actual = websocket.request_headers.get("X-MetaAgent-Token", "")
    return actual == required_token


async def websocket_handler(
    websocket: WebSocketServerProtocol,
    path: str,
    required_token: str,
) -> None:
    if path != "/ws/pc-agent":
        await websocket.close(code=1008, reason="Unsupported path")
        return
    if not _is_authorized(websocket, required_token):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    subscribed_session_ids: set[str] = set()

    try:
        async for raw_message in websocket:
            print(f"[pc-agent] received raw frame: {raw_message}")
            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                await send_event(
                    websocket,
                    event="pc.session.failed",
                    task_id=None,
                    node_id=None,
                    session_id=None,
                    payload={"message": "Invalid JSON payload", "error": "Invalid JSON payload"},
                )
                continue

            request = PcSessionRequest.from_dict(payload)
            print(
                "[pc-agent] parsed request "
                f"type={request.type!r} method={request.method!r} task_id={request.task_id!r} "
                f"node_id={request.node_id!r} session_id={request.session_id!r}"
            )

            if request.type != "req":
                await send_event(
                    websocket,
                    event="pc.session.failed",
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "message": f"Unsupported frame type: {request.type}",
                        "error": f"Unsupported frame type: {request.type}",
                    },
                )
                continue

            if request.method == "pc.session.start":
                session_id = await handle_start_request(websocket, request)
                subscribed_session_ids.add(session_id)
                continue

            if request.method == "pc.session.input":
                session_id = await handle_input_request(websocket, request)
                if session_id:
                    subscribed_session_ids.add(session_id)
                continue

            if request.method == "pc.session.snapshot":
                session_id = await handle_snapshot_request(websocket, request)
                if session_id:
                    subscribed_session_ids.add(session_id)
                continue

            if request.method == "pc.session.cancel":
                session_id = await handle_cancel_request(websocket, request)
                if session_id:
                    subscribed_session_ids.add(session_id)
                continue

            await send_event(
                websocket,
                event="pc.session.failed",
                task_id=request.task_id,
                node_id=request.node_id,
                session_id=request.session_id,
                payload={
                    "message": f"Unsupported method: {request.method}",
                    "error": f"Unsupported method: {request.method}",
                },
            )
    except ConnectionClosed:
        return
    finally:
        for session_id in subscribed_session_ids:
            _unsubscribe(session_id, websocket)


async def run_server(host: str, port: int, token: str) -> None:
    async with serve(lambda ws, path: websocket_handler(ws, path, token), host, port):
        print(f"MetaAgent PC Orchestrator listening on ws://{host}:{port}/ws/pc-agent")
        await asyncio.Future()


def main() -> None:
    args = parse_args()
    asyncio.run(run_server(args.host, args.port, args.token.strip()))
