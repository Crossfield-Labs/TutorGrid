from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.config import get_runtime_config_view, update_memory_config, update_planner_config
from backend.config import load_config
from backend.memory.service import MemoryService
from backend.runners.router import RunnerRouter
from backend.server.protocol import OrchestratorRequest, build_event
from backend.sessions.manager import SessionManager
from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


ROOT = Path(__file__).resolve().parents[2]
TRACE_ROOT = ROOT / "scratch" / "session-trace"
session_manager = SessionManager()
trace_store = JsonlTraceStore(TRACE_ROOT)
memory_service = MemoryService()
runner_router = RunnerRouter()
session_waiters: dict[str, asyncio.Future[str]] = {}
session_tasks: dict[str, asyncio.Task[None]] = {}
session_subscribers: dict[str, set[WebSocketServerProtocol]] = defaultdict(set)
subscriber_event_namespaces: dict[WebSocketServerProtocol, str] = {}


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


def _ensure_workspace(raw_workspace: str) -> str:
    workspace_text = raw_workspace.strip() or str(ROOT / "scratch" / "orchestrator-session")
    workspace_path = Path(workspace_text).expanduser()
    workspace_path.mkdir(parents=True, exist_ok=True)
    return str(workspace_path)


def _should_trace_event(event: str) -> bool:
    return event != "orchestrator.session.snapshot"


def _build_trace_payload(event: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if event == "orchestrator.session.snapshot":
        snapshot = payload.get("snapshot") or {}
        return {
            "message": payload.get("message", ""),
            "runner": payload.get("runner", ""),
            "snapshotVersion": snapshot.get("snapshotVersion"),
            "phase": snapshot.get("phase", ""),
            "activeWorker": snapshot.get("activeWorker", ""),
            "activeWorkerProfile": snapshot.get("activeWorkerProfile", ""),
            "activeWorkerCanInterrupt": snapshot.get("activeWorkerCanInterrupt", False),
            "latestSummary": snapshot.get("latestSummary", ""),
            "latestArtifactSummary": snapshot.get("latestArtifactSummary", ""),
            "permissionSummary": snapshot.get("permissionSummary", ""),
            "sessionInfoSummary": snapshot.get("sessionInfoSummary", ""),
            "mcpStatusSummary": snapshot.get("mcpStatusSummary", ""),
        }
    return payload


def _append_session_trace(
    session: OrchestratorSessionState,
    *,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    if not _should_trace_event(event):
        return
    trace_store.append_session_event(session, event=event, payload=_build_trace_payload(event, payload))


def _translate_event_name(event: str, namespace: str) -> str:
    if namespace == "pc" and event.startswith("orchestrator.session."):
        return "pc.session." + event.removeprefix("orchestrator.session.")
    return event


def _subscribe(session_id: str, websocket: WebSocketServerProtocol, namespace: str) -> None:
    session_subscribers[session_id].add(websocket)
    subscriber_event_namespaces[websocket] = namespace


def _unsubscribe(session_id: str, websocket: WebSocketServerProtocol) -> None:
    subscribers = session_subscribers.get(session_id)
    if not subscribers:
        return
    subscribers.discard(websocket)
    if not subscribers:
        session_subscribers.pop(session_id, None)
    if all(websocket not in items for items in session_subscribers.values()):
        subscriber_event_namespaces.pop(websocket, None)


async def _broadcast_event(
    session: OrchestratorSessionState,
    *,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    _append_session_trace(session, event=event, payload=payload)
    stale: list[WebSocketServerProtocol] = []
    for websocket in list(session_subscribers.get(session.session_id, set())):
        try:
            await send_event(
                websocket,
                event=_translate_event_name(event, subscriber_event_namespaces.get(websocket, "orchestrator")),
                task_id=session.task_id,
                node_id=session.node_id,
                session_id=session.session_id,
                payload=payload,
            )
        except ConnectionClosed:
            stale.append(websocket)
    for websocket in stale:
        _unsubscribe(session.session_id, websocket)


def _build_explanation_message(session: OrchestratorSessionState) -> str:
    snapshot = session.build_snapshot()
    lines: list[str] = [f"当前会话状态：{snapshot['status']}，阶段：{snapshot['phase']}。"]
    if snapshot["activeWorker"]:
        worker_line = f"当前 worker：{snapshot['activeWorker']}"
        if snapshot["activeSessionMode"]:
            worker_line += f"（session_mode={snapshot['activeSessionMode']}）"
        if snapshot["activeWorkerProfile"]:
            worker_line += f"（profile={snapshot['activeWorkerProfile']}）"
        lines.append(worker_line + "。")
    if snapshot["activeWorkerTaskId"]:
        lines.append(f"当前 worker task_id：{snapshot['activeWorkerTaskId']}")
    if snapshot["activeWorkerCanInterrupt"]:
        lines.append("当前 worker 支持 interrupt。")
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
    if snapshot["permissionSummary"]:
        lines.append(f"权限情况：{snapshot['permissionSummary']}")
    if snapshot["sessionInfoSummary"]:
        lines.append(f"会话信息：{snapshot['sessionInfoSummary']}")
    if snapshot["mcpStatusSummary"]:
        lines.append(f"MCP 情况：{snapshot['mcpStatusSummary']}")
    recent_hooks = snapshot.get("recentHookEvents") or []
    if recent_hooks:
        latest_hook = recent_hooks[-1]
        hook_name = str(latest_hook.get("name") or "").strip()
        hook_message = str(latest_hook.get("message") or "").strip()
        if hook_name or hook_message:
            lines.append(f"最近 hook：{hook_name or 'hook'} - {hook_message}")
    if snapshot["artifacts"]:
        lines.append(f"当前已记录产物 {len(snapshot['artifacts'])} 个。")
    return "\n".join(lines)


def _classify_input_handling(*, input_intent: str, waiter_active: bool) -> str:
    normalized_intent = (input_intent or "reply").strip().lower() or "reply"
    if normalized_intent == "explain":
        return "explain"
    if normalized_intent == "interrupt":
        return "interrupt"
    if waiter_active:
        if normalized_intent == "reply":
            return "reply_waiter"
        if normalized_intent in {"redirect", "comment", "instruction"}:
            return "queue_followup"
        return "unsupported_waiter"
    if normalized_intent == "reply":
        return "reply_without_waiter"
    if normalized_intent in {"redirect", "comment", "instruction"}:
        return "queue_followup"
    return "unsupported"


async def _emit_projection_updates(session: OrchestratorSessionState) -> None:
    snapshot = session.build_snapshot()
    previous = session.context.get("_projection_state")
    previous_state = previous if isinstance(previous, dict) else {}

    if previous_state.get("phase") != snapshot["phase"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.phase",
            payload={
                "phase": snapshot["phase"],
                "message": snapshot["latestSummary"] or snapshot["lastProgressMessage"],
                "snapshot": snapshot,
            },
        )

    current_worker = {
        "worker": snapshot["activeWorker"],
        "sessionMode": snapshot["activeSessionMode"],
        "workerProfile": snapshot["activeWorkerProfile"],
        "taskId": snapshot["activeWorkerTaskId"],
        "canInterrupt": snapshot["activeWorkerCanInterrupt"],
    }
    previous_worker = {
        "worker": previous_state.get("activeWorker", ""),
        "sessionMode": previous_state.get("activeSessionMode", ""),
        "workerProfile": previous_state.get("activeWorkerProfile", ""),
        "taskId": previous_state.get("activeWorkerTaskId", ""),
        "canInterrupt": previous_state.get("activeWorkerCanInterrupt", False),
    }
    if current_worker != previous_worker and snapshot["activeWorker"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.worker",
            payload={
                "worker": snapshot["activeWorker"],
                "sessionMode": snapshot["activeSessionMode"],
                "workerProfile": snapshot["activeWorkerProfile"],
                "taskId": snapshot["activeWorkerTaskId"],
                "canInterrupt": snapshot["activeWorkerCanInterrupt"],
                "message": snapshot["latestSummary"] or snapshot["lastProgressMessage"],
                "snapshot": snapshot,
            },
        )

    if previous_state.get("latestSummary") != snapshot["latestSummary"] and snapshot["latestSummary"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.summary",
            payload={"message": snapshot["latestSummary"], "phase": snapshot["phase"], "snapshot": snapshot},
        )

    if (
        previous_state.get("latestArtifactSummary") != snapshot["latestArtifactSummary"]
        and snapshot["latestArtifactSummary"]
    ):
        await _broadcast_event(
            session,
            event="orchestrator.session.artifact_summary",
            payload={
                "message": snapshot["latestArtifactSummary"],
                "artifacts": snapshot["artifacts"],
                "phase": snapshot["phase"],
                "snapshot": snapshot,
            },
        )

    if previous_state.get("permissionSummary") != snapshot["permissionSummary"] and snapshot["permissionSummary"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.permission",
            payload={
                "message": snapshot["permissionSummary"],
                "phase": snapshot["phase"],
                "worker": snapshot["activeWorker"],
                "snapshot": snapshot,
            },
        )

    if previous_state.get("mcpStatusSummary") != snapshot["mcpStatusSummary"] and snapshot["mcpStatusSummary"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.mcp_status",
            payload={
                "message": snapshot["mcpStatusSummary"],
                "phase": snapshot["phase"],
                "worker": snapshot["activeWorker"],
                "snapshot": snapshot,
            },
        )

    if previous_state.get("sessionInfoSummary") != snapshot["sessionInfoSummary"] and snapshot["sessionInfoSummary"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.worker_runtime",
            payload={
                "message": snapshot["sessionInfoSummary"],
                "worker": snapshot["activeWorker"],
                "workerProfile": snapshot["activeWorkerProfile"],
                "taskId": snapshot["activeWorkerTaskId"],
                "canInterrupt": snapshot["activeWorkerCanInterrupt"],
                "snapshot": snapshot,
            },
        )

    if previous_state.get("snapshotVersion") != snapshot["snapshotVersion"]:
        await _broadcast_event(
            session,
            event="orchestrator.session.snapshot",
            payload={"message": snapshot["latestSummary"] or snapshot["lastProgressMessage"], "snapshot": snapshot},
        )

    session.context["_projection_state"] = {
        "phase": snapshot["phase"],
        "activeWorker": snapshot["activeWorker"],
        "activeSessionMode": snapshot["activeSessionMode"],
        "activeWorkerProfile": snapshot["activeWorkerProfile"],
        "activeWorkerTaskId": snapshot["activeWorkerTaskId"],
        "activeWorkerCanInterrupt": snapshot["activeWorkerCanInterrupt"],
        "latestSummary": snapshot["latestSummary"],
        "latestArtifactSummary": snapshot["latestArtifactSummary"],
        "permissionSummary": snapshot["permissionSummary"],
        "sessionInfoSummary": snapshot["sessionInfoSummary"],
        "mcpStatusSummary": snapshot["mcpStatusSummary"],
        "snapshotVersion": snapshot["snapshotVersion"],
    }


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
    await _emit_projection_updates(session)

    async def emit_progress(message: str, progress: float | None = None) -> None:
        session.mark(status="RUNNING", message=message)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.progress",
            payload={
                "message": message,
                "progress": progress,
                "runner": session.runner,
                "snapshot": session.build_snapshot(),
            },
        )
        await _emit_projection_updates(session)

    async def await_user(message: str, input_mode: str | None = None) -> str:
        session.request_user_input(message, input_mode or "text")
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.await_user",
            payload={
                "message": message,
                "inputMode": input_mode or "text",
                "runner": session.runner,
                "snapshot": session.build_snapshot(),
            },
        )
        await _emit_projection_updates(session)
        reply = await _await_user(session.session_id, message, input_mode or "text")
        session.resume_with_input(reply)
        session_manager.update(session)
        await emit_progress(f"User replied: {reply}", 0.62)
        await _emit_projection_updates(session)
        return reply

    async def emit_substep(kind: str, title: str, status: str, detail: str | None = None) -> None:
        record = {"kind": kind, "title": title, "status": status, "detail": detail or ""}
        session.substeps.append(record)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event=f"orchestrator.session.subnode.{status}",
            payload={
                "kind": kind,
                "title": title,
                "status": status,
                "message": detail or title,
                "detail": detail or "",
                "snapshot": session.build_snapshot(),
            },
        )
        await _emit_projection_updates(session)

    try:
        if hasattr(runner, "set_event_callbacks"):
            runner.set_event_callbacks(emit_substep=emit_substep)
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
            payload={
                "message": "Session completed",
                "result": result,
                "runner": session.runner,
                "progress": 1.0,
                "artifacts": session.artifacts,
                "workerRuns": session.worker_runs,
                "snapshot": session.build_snapshot(),
            },
        )
        _maybe_compact_memory(session, reason="completed")
        await _emit_projection_updates(session)
    except asyncio.CancelledError:
        session.error = "Session cancelled"
        session.phase = "cancelled"
        session.stop_reason = "cancelled"
        session.mark(status="CANCELLED", message=session.error)
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.failed",
            payload={"message": session.error, "error": session.error, "runner": session.runner, "snapshot": session.build_snapshot()},
        )
        await _emit_projection_updates(session)
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
            payload={"message": session.error, "error": session.error, "runner": session.runner, "snapshot": session.build_snapshot()},
        )
        _maybe_compact_memory(session, reason="failed")
        await _emit_projection_updates(session)
    finally:
        session_waiters.pop(session.session_id, None)
        session_tasks.pop(session.session_id, None)


def _maybe_compact_memory(session: OrchestratorSessionState, *, reason: str) -> None:
    config = load_config()
    memory = config.memory
    if not memory.enabled or not memory.auto_compact:
        return
    if reason == "completed" and not memory.compact_on_complete:
        return
    if reason == "failed" and not memory.compact_on_failure:
        return
    history_items = trace_store.list_session_history(session.session_id, limit=500)
    memory_service.compact_session(
        session_id=session.session_id,
        task=session.task,
        goal=session.goal,
        history_items=history_items,
    )


def _is_authorized(websocket: WebSocketServerProtocol, required_token: str) -> bool:
    if not required_token:
        return True
    actual = websocket.request_headers.get("X-MetaAgent-Token", "")
    return actual == required_token


async def websocket_handler(websocket: WebSocketServerProtocol, path: str, required_token: str) -> None:
    global runner_router
    if path not in {"/ws/orchestrator", "/ws/pc-agent"}:
        await websocket.close(code=1008, reason="Unsupported path")
        return
    if not _is_authorized(websocket, required_token):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    event_namespace = "pc" if path == "/ws/pc-agent" else "orchestrator"

    subscribed_session_ids: set[str] = set()

    try:
        async for raw_message in websocket:
            def event_name(name: str) -> str:
                return _translate_event_name(name, event_namespace)

            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.failed"),
                    task_id=None,
                    node_id=None,
                    session_id=None,
                    payload={"message": "Invalid JSON payload", "error": "Invalid JSON payload"},
                )
                continue
            request = OrchestratorRequest.from_dict(payload)
            if request.type != "req":
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.failed"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "message": f"Unsupported frame type: {request.type}",
                        "error": f"Unsupported frame type: {request.type}",
                    },
                )
                continue

            if request.method in {"orchestrator.session.start", "pc.session.start"}:
                task_text = request.params.task.strip() or request.params.goal.strip()
                session = session_manager.create(
                    task_id=request.task_id or "task",
                    node_id=request.node_id or "node",
                    runner=request.params.runner,
                    workspace=_ensure_workspace(request.params.workspace),
                    task=task_text,
                    goal=request.params.goal,
                )
                if request.params.command:
                    session.context["command"] = request.params.command
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                session_task = asyncio.create_task(_run_session(session.session_id, websocket))
                session_tasks[session.session_id] = session_task
                continue

            if request.method in {"orchestrator.session.list", "pc.session.list"}:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={"items": session_manager.list_sessions(limit=max(1, request.params.limit or 50))},
                )
                continue

            if request.method in {"orchestrator.config.get", "pc.config.get"}:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.config.get"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=get_runtime_config_view(),
                )
                continue

            if request.method in {"orchestrator.config.set", "pc.config.set"}:
                update_planner_config(
                    provider=request.params.provider.strip() or "openai_compat",
                    model=request.params.model.strip(),
                    api_key=request.params.api_key.strip(),
                    api_base=request.params.api_base.strip(),
                )
                update_memory_config(
                    enabled=request.params.memory_enabled,
                    auto_compact=request.params.memory_auto_compact,
                    compact_on_complete=request.params.memory_compact_on_complete,
                    compact_on_failure=request.params.memory_compact_on_failure,
                    retrieval_scope=request.params.memory_retrieval_scope.strip() or "global",
                    retrieval_strength=request.params.memory_retrieval_strength.strip() or "standard",
                    cleanup_enabled=request.params.memory_cleanup_enabled,
                    cleanup_interval_hours=max(1, request.params.memory_cleanup_interval_hours),
                )
                runner_router = RunnerRouter()
                await send_event(
                    websocket,
                    event=event_name("orchestrator.config.set"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "message": "Config updated",
                        **get_runtime_config_view(),
                    },
                )
                continue

            if request.method in {"orchestrator.session.history", "pc.session.history"} and request.session_id:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.history"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": trace_store.list_session_history(
                            request.session_id,
                            limit=max(1, request.params.limit or 200),
                        )
                    },
                )
                continue

            if request.method in {"orchestrator.memory.compact", "pc.memory.compact"} and request.session_id:
                snapshot = session_manager.get_snapshot(request.session_id)
                if snapshot is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                history_items = trace_store.list_session_history(
                    request.session_id,
                    limit=max(1, request.params.limit or 500),
                )
                payload = memory_service.compact_session(
                    session_id=request.session_id,
                    task=str(snapshot.get("task") or ""),
                    goal=str(snapshot.get("goal") or ""),
                    history_items=history_items,
                )
                await send_event(
                    websocket,
                    event=event_name("orchestrator.memory.compact"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.memory.search", "pc.memory.search"}:
                results = memory_service.search(
                    query=request.params.text,
                    limit=max(1, request.params.limit or 5),
                    session_id=request.session_id or None,
                )
                await send_event(
                    websocket,
                    event=event_name("orchestrator.memory.search"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "query": request.params.text,
                        "items": [
                            {
                                "documentId": item.document_id,
                                "sessionId": item.session_id,
                                "documentType": item.document_type,
                                "title": item.title,
                                "content": item.content,
                                "metadata": item.metadata,
                                "score": item.score,
                                "updatedAt": item.updated_at,
                            }
                            for item in results
                        ],
                    },
                )
                continue

            if request.method in {"orchestrator.session.input", "pc.session.input"} and request.session_id:
                session = session_manager.get(request.session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                input_intent = (request.params.input_intent or "reply").strip().lower() or "reply"
                waiter = session_waiters.get(request.session_id)
                action = _classify_input_handling(
                    input_intent=input_intent,
                    waiter_active=bool(waiter is not None and not waiter.done()),
                )
                if action == "explain":
                    explanation = _build_explanation_message(session)
                    await _broadcast_event(
                        session,
                        event="orchestrator.session.summary",
                        payload={"message": explanation, "snapshot": session.build_snapshot()},
                    )
                    await _emit_projection_updates(session)
                elif action == "reply_waiter":
                    waiter.set_result(request.params.text)
                    await _broadcast_event(
                        session,
                        event="orchestrator.session.followup.accepted",
                        payload={
                            "message": "Accepted user reply.",
                            "intent": input_intent,
                            "text": request.params.text,
                        },
                    )
                    await _emit_projection_updates(session)
                elif action == "reply_without_waiter":
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=session.task_id,
                        node_id=session.node_id,
                        session_id=session.session_id,
                        payload={"message": "Session is not waiting for user input"},
                    )
                elif action == "queue_followup":
                    if not request.params.text.strip():
                        await send_event(
                            websocket,
                            event=event_name("orchestrator.session.failed"),
                            task_id=session.task_id,
                            node_id=session.node_id,
                            session_id=session.session_id,
                            payload={"message": "Follow-up text cannot be empty", "error": "Follow-up text cannot be empty"},
                        )
                        continue
                    session_manager.enqueue_followup(
                        request.session_id,
                        text=request.params.text,
                        intent=input_intent,
                        target=request.params.target,
                    )
                    await _broadcast_event(
                        session,
                        event="orchestrator.session.followup.accepted",
                        payload={
                            "message": "Accepted follow-up for the current session.",
                            "intent": input_intent,
                            "text": request.params.text,
                            "target": request.params.target,
                            "runner": session.runner,
                            "followup": {"text": request.params.text, "intent": input_intent, "target": request.params.target},
                            "snapshot": session.build_snapshot(),
                        },
                    )
                    await _emit_projection_updates(session)
                elif action == "unsupported_waiter":
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=session.task_id,
                        node_id=session.node_id,
                        session_id=session.session_id,
                        payload={"message": f"Unsupported input intent while waiting for input: {input_intent}"},
                    )
                else:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=session.task_id,
                        node_id=session.node_id,
                        session_id=session.session_id,
                        payload={"message": f"Unsupported input intent: {input_intent}"},
                    )
                continue

            if request.method in {"orchestrator.session.snapshot", "pc.session.snapshot"} and request.session_id:
                session = session_manager.get(request.session_id)
                snapshot = session_manager.get_snapshot(request.session_id)
                if snapshot is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                if session is not None:
                    _subscribe(session.session_id, websocket, event_namespace)
                    subscribed_session_ids.add(session.session_id)
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.snapshot"),
                    task_id=session.task_id if session is not None else request.task_id,
                    node_id=session.node_id if session is not None else request.node_id,
                    session_id=request.session_id,
                    payload={
                        "snapshot": snapshot,
                        "message": str(
                            snapshot.get("latestSummary") or snapshot.get("lastProgressMessage") or ""
                        ),
                        "runner": str(snapshot.get("runner") or ""),
                    },
                )
                continue

            if request.method in {"orchestrator.session.cancel", "pc.session.cancel"} and request.session_id:
                task = session_tasks.get(request.session_id)
                if task is not None:
                    task.cancel()
                continue

            if request.method in {"orchestrator.session.interrupt", "pc.session.interrupt"} and request.session_id:
                session = session_manager.get(request.session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                control = session.context.get("_active_worker_control")
                if control is None or not getattr(control, "can_interrupt", False) or getattr(control, "interrupt", None) is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=session.task_id,
                        node_id=session.node_id,
                        session_id=session.session_id,
                        payload={
                            "message": "The active worker does not currently support interrupt.",
                            "error": "The active worker does not currently support interrupt.",
                        },
                    )
                    continue
                result = await control.interrupt()
                session.stop_reason = "interrupt_requested"
                session.latest_summary = request.params.text or "Interrupt requested."
                session.phase = "interrupting"
                session_manager.update(session)
                await _broadcast_event(
                    session,
                    event="orchestrator.session.followup.accepted",
                    payload={
                        "message": session.latest_summary,
                        "intent": "interrupt",
                        "text": request.params.text,
                        "runner": session.runner,
                        "worker": getattr(control, "worker", ""),
                        "result": result,
                        "snapshot": session.build_snapshot(),
                    },
                )
                await _emit_projection_updates(session)
                continue

            await send_event(
                websocket,
                event=event_name("orchestrator.session.failed"),
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


