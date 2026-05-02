from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from backend.config import (
    get_runtime_config_view,
    update_langsmith_config,
    update_memory_config,
    update_planner_config,
    update_push_config,
    update_search_config,
)
from backend.config import load_config
from backend.editor import TipTapAICommandService
from backend.observability import reset_langsmith_tracer
from backend.scheduler.service import LearningPushScheduler
from backend.knowledge.service import KnowledgeBaseService
from backend.learning_profile.service import LearningProfileService
from backend.memory.service import MemoryService
from backend.profile.service import LearningProfileService as LegacyLearningProfileService
from backend.rag.service import RagService
from backend.runners.router import RunnerRouter
from backend.runtime.runtime import RuntimePaused
from backend.server.protocol import OrchestratorRequest, build_event
from backend.sessions.manager import SessionManager
from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore
from backend.storage.models import build_artifact_rows
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


ROOT = Path(__file__).resolve().parents[2]
TRACE_ROOT = ROOT / "scratch" / "session-trace"
session_manager = SessionManager()
trace_store = JsonlTraceStore(TRACE_ROOT)
memory_service = MemoryService()
profile_service = LegacyLearningProfileService()
push_scheduler = LearningPushScheduler()
tiptap_service = TipTapAICommandService()
knowledge_service = KnowledgeBaseService()
learning_profile_service = LearningProfileService()
rag_service = RagService(knowledge_service=knowledge_service)
runner_router = RunnerRouter()
session_waiters: dict[str, asyncio.Future[str]] = {}
session_tasks: dict[str, asyncio.Task[None]] = {}
session_subscribers: dict[str, set[WebSocketServerProtocol]] = defaultdict(set)
subscriber_event_namespaces: dict[WebSocketServerProtocol, str] = {}
_last_memory_cleanup_monotonic = 0.0

TASK_STEP_ORDER = ("planning", "tools", "verify", "finalize")
TASK_STEP_LABELS = {
    "planning": "规划任务",
    "tools": "执行工具",
    "verify": "验证结果",
    "finalize": "整理输出",
}


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
    seq: int | None = None,
) -> None:
    await websocket.send(
        json.dumps(
            build_event(
                event=event,
                task_id=task_id,
                node_id=node_id,
                session_id=session_id,
                payload=payload,
                seq=seq,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
            ensure_ascii=False,
        )
    )


def _get_task_doc_id(session: OrchestratorSessionState) -> str:
    return str(session.context.get("doc_id") or "")


def _merge_request_context(
    session: OrchestratorSessionState,
    context: dict[str, Any] | None,
) -> None:
    merged = dict(context or {})
    session.context["task_context"] = merged
    for key, value in merged.items():
        if not str(key).strip():
            continue
        session.context[str(key)] = value


def _normalize_task_status(status: str) -> str:
    normalized = (status or "").strip().upper()
    if normalized == "COMPLETED":
        return "done"
    if normalized == "FAILED":
        return "failed"
    if normalized == "CANCELLED":
        return "failed"
    if normalized == "RUNNING":
        return "running"
    return "pending"


def _resolve_task_phase(session: OrchestratorSessionState) -> str:
    phase = (session.phase or "").strip().lower()
    if phase in TASK_STEP_ORDER:
        return phase
    if phase in {"created", "starting", "awaiting_user"}:
        return "planning"
    if phase in {"interrupting"}:
        return "tools"
    if phase in {"completed", "cancelled", "failed"}:
        return "finalize"
    return "tools"


def _build_task_steps(
    *,
    current_phase: str,
    task_status: str,
    failed_phase: str | None = None,
) -> list[dict[str, Any]]:
    current_index = TASK_STEP_ORDER.index(current_phase)
    failed_phase = failed_phase or ""
    failed_index = TASK_STEP_ORDER.index(failed_phase) if failed_phase in TASK_STEP_ORDER else -1
    items: list[dict[str, Any]] = []
    for index, phase in enumerate(TASK_STEP_ORDER):
        status = "pending"
        if task_status == "done":
            status = "done"
        elif task_status == "failed":
            if index < failed_index:
                status = "done"
            elif index == failed_index:
                status = "failed"
        elif task_status == "awaiting_user":
            if index < current_index:
                status = "done"
            elif index == current_index:
                status = "awaiting_user"
        elif task_status == "interrupted":
            if index < current_index:
                status = "done"
            elif index == current_index:
                status = "interrupted"
        else:
            if index < current_index:
                status = "done"
            elif index == current_index:
                status = "running"
        items.append(
            {
                "phase": phase,
                "name": TASK_STEP_LABELS[phase],
                "status": status,
                "index": index + 1,
            }
        )
    return items


async def _broadcast_task_step(
    session: OrchestratorSessionState,
    *,
    summary: str,
    status: str | None = None,
    phase: str | None = None,
) -> None:
    current_phase = phase or _resolve_task_phase(session)
    task_status = status or _normalize_task_status(session.status)
    current_index = TASK_STEP_ORDER.index(current_phase) + 1
    await _broadcast_event(
        session,
        event="orchestrator.task.step",
        payload={
            "task_id": session.task_id,
            "session_id": session.session_id,
            "doc_id": _get_task_doc_id(session),
            "step_index": current_index,
            "step_total": len(TASK_STEP_ORDER),
            "step_name": TASK_STEP_LABELS[current_phase],
            "phase": current_phase,
            "status": task_status,
            "summary": summary,
            "awaiting_user": task_status == "awaiting_user",
            "steps": _build_task_steps(
                current_phase=current_phase,
                task_status=task_status,
                failed_phase=current_phase if task_status == "failed" else None,
            ),
        },
    )


def _build_task_artifacts(session: OrchestratorSessionState) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in session.artifacts:
        suffix = Path(str(path)).suffix.lower()
        artifact_type = "file"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            artifact_type = "image"
        elif suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".csv"}:
            artifact_type = "code"
        items.append(
            {
                "type": artifact_type,
                "path": path,
            }
        )
    return items


def _resolve_task_result_type(session: OrchestratorSessionState) -> str:
    if any(run.get("worker") == "python_runner" for run in session.worker_runs):
        return "code_output"
    if session.artifacts:
        return "artifact"
    return "text"


def _build_task_result_payload(
    session: OrchestratorSessionState,
    *,
    status: str,
    content: str,
    error_code: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": session.task_id,
        "session_id": session.session_id,
        "doc_id": _get_task_doc_id(session),
        "status": status,
        "result_type": _resolve_task_result_type(session) if status == "done" else "error",
        "content": content,
        "artifacts": _build_task_artifacts(session),
        "worker_runs": list(session.worker_runs),
    }
    if error_code:
        payload["error_code"] = error_code
    return payload


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


def _next_event_seq(session: OrchestratorSessionState) -> int:
    sequence = int(session.context.get("_event_sequence") or 0) + 1
    session.context["_event_sequence"] = sequence
    return sequence


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
    seq = _next_event_seq(session)
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
                seq=seq,
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


def _build_artifact_tiles(session: OrchestratorSessionState) -> list[dict[str, Any]]:
    return [
        {
            "path": row["path"],
            "title": Path(str(row["path"])).name or str(row["path"]),
            "changeType": row["change_type"],
            "size": row["size"],
            "summary": row["summary"],
            "createdAt": row["created_at"],
        }
        for row in build_artifact_rows(session)
    ]


async def _emit_artifact_projection_updates(
    session: OrchestratorSessionState,
    *,
    previous_tiles: list[dict[str, Any]],
    current_tiles: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> None:
    previous_by_path = {str(item.get("path") or ""): item for item in previous_tiles if item.get("path")}
    current_by_path = {str(item.get("path") or ""): item for item in current_tiles if item.get("path")}

    for path in sorted(set(current_by_path) - set(previous_by_path)):
        tile = current_by_path[path]
        await _broadcast_event(
            session,
            event="orchestrator.session.artifact.created",
            payload={"message": tile.get("summary") or tile.get("title") or path, "artifact": tile, "snapshot": snapshot},
        )

    for path in sorted(set(current_by_path).intersection(previous_by_path)):
        if current_by_path[path] == previous_by_path[path]:
            continue
        tile = current_by_path[path]
        await _broadcast_event(
            session,
            event="orchestrator.session.artifact.updated",
            payload={"message": tile.get("summary") or tile.get("title") or path, "artifact": tile, "snapshot": snapshot},
        )

    for path in sorted(set(previous_by_path) - set(current_by_path)):
        await _broadcast_event(
            session,
            event="orchestrator.session.artifact.removed",
            payload={"message": path, "artifact": {"path": path}, "snapshot": snapshot},
        )

    if previous_tiles != current_tiles:
        await _broadcast_event(
            session,
            event="orchestrator.session.tile",
            payload={
                "message": snapshot["latestArtifactSummary"] or f"{len(current_tiles)} artifact tile(s) available",
                "tiles": current_tiles,
                "snapshot": snapshot,
            },
        )


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


def _can_accept_followup(session: OrchestratorSessionState) -> bool:
    task = session_tasks.get(session.session_id)
    return session.status.upper() == "RUNNING" and task is not None and not task.done()


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


async def _emit_projection_updates(session: OrchestratorSessionState) -> None:
    snapshot = session.build_snapshot()
    previous = session.context.get("_projection_state")
    previous_state = previous if isinstance(previous, dict) else {}
    current_tiles = _build_artifact_tiles(session)
    previous_tiles = list(previous_state.get("artifactTiles") or [])

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

    await _emit_artifact_projection_updates(
        session,
        previous_tiles=previous_tiles,
        current_tiles=current_tiles,
        snapshot=snapshot,
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
        "artifactTiles": current_tiles,
    }


async def _run_session(session_id: str, websocket: WebSocketServerProtocol) -> None:
    session = session_manager.get(session_id)
    if session is None:
        return

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
        if session.awaiting_input:
            last_broadcast_prompt = str(session.context.get("_last_awaiting_prompt_broadcast") or "")
            if session.pending_user_prompt and session.pending_user_prompt != last_broadcast_prompt:
                session.context["_last_awaiting_prompt_broadcast"] = session.pending_user_prompt
                await _broadcast_event(
                    session,
                    event="orchestrator.session.await_user",
                    payload={
                        "message": session.pending_user_prompt,
                        "inputMode": str(session.context.get("pending_user_input_mode") or "text"),
                        "runner": session.runner,
                        "snapshot": session.build_snapshot(),
                    },
                )
                await _broadcast_event(
                    session,
                    event="orchestrator.task.awaiting_user",
                    payload={
                        "task_id": session.task_id,
                        "session_id": session.session_id,
                        "doc_id": _get_task_doc_id(session),
                        "prompt": session.pending_user_prompt,
                        "resume_method": "orchestrator.task.resume",
                        "input_mode": str(session.context.get("pending_user_input_mode") or "text"),
                    },
                )
            await _broadcast_task_step(
                session,
                summary=session.pending_user_prompt or message,
                status="awaiting_user",
                phase="tools",
            )
        else:
            await _broadcast_task_step(session, summary=message, status="running", phase=_resolve_task_phase(session))
        await _emit_projection_updates(session)

    async def await_user(message: str, input_mode: str | None = None) -> str:
        session.request_user_input(message, input_mode or "text")
        session.context["pending_user_input_mode"] = input_mode or "text"
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
        await _broadcast_event(
            session,
            event="orchestrator.task.awaiting_user",
            payload={
                "task_id": session.task_id,
                "session_id": session.session_id,
                "doc_id": _get_task_doc_id(session),
                "prompt": message,
                "resume_method": "orchestrator.task.resume",
                "input_mode": input_mode or "text",
            },
        )
        await _broadcast_task_step(session, summary=message, status="awaiting_user", phase="tools")
        await _emit_projection_updates(session)
        reply = await _await_user(session.session_id, message, input_mode or "text")
        session.resume_with_input(reply)
        session.context.pop("pending_user_input_mode", None)
        session.context.pop("_last_awaiting_prompt_broadcast", None)
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

    async def emit_message_event(kind: str, payload: dict[str, Any]) -> None:
        session_manager.update(session)
        await _broadcast_event(
            session,
            event=f"orchestrator.session.message.{kind}",
            payload={
                **payload,
                "snapshot": session.build_snapshot(),
            },
        )

    try:
        runner = runner_router.get(session.runner)
        session.phase = "starting"
        session.mark(status="RUNNING", message="Session started")
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.started",
            payload={"message": "session started", "runner": session.runner, "snapshot": session.build_snapshot()},
        )
        await _broadcast_task_step(session, summary="任务已创建，开始规划。", status="running", phase="planning")
        await _emit_projection_updates(session)
        if hasattr(runner, "set_event_callbacks"):
            runner.set_event_callbacks(emit_substep=emit_substep, emit_message_event=emit_message_event)
        result = await runner.run(session, emit_progress, await_user)
        session.result = result
        session.phase = "finalize"
        session.stop_reason = "completed"
        session.mark(status="COMPLETED", message="Session completed")
        session.latest_summary = result[:400] if result else "Session completed"
        session_manager.update(session)
        await _broadcast_task_step(
            session,
            summary=session.latest_summary or "任务已完成。",
            status="done",
            phase="finalize",
        )
        session.phase = "completed"
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
        await _broadcast_event(
            session,
            event="orchestrator.task.result",
            payload=_build_task_result_payload(session, status="done", content=result),
        )
        _maybe_compact_memory(session, reason="completed")
        profiles = _refresh_learning_profiles(session, reason="completed")
        await _maybe_generate_learning_pushes(session, reason="completed", profiles=profiles)
        await _emit_projection_updates(session)
    except asyncio.CancelledError:
        session.error = "Session cancelled"
        session.phase = "finalize"
        session.stop_reason = "cancelled"
        session.mark(status="CANCELLED", message=session.error)
        session_manager.update(session)
        await _broadcast_task_step(session, summary=session.error, status="failed", phase="finalize")
        session.phase = "cancelled"
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.failed",
            payload={"message": session.error, "error": session.error, "runner": session.runner, "snapshot": session.build_snapshot()},
        )
        await _broadcast_event(
            session,
            event="orchestrator.task.result",
            payload=_build_task_result_payload(
                session,
                status="failed",
                content=session.error,
                error_code="cancelled",
            ),
        )
        await _emit_projection_updates(session)
        raise
    except RuntimePaused as pause:
        session.phase = "awaiting_user"
        session.awaiting_input = True
        session.pending_user_prompt = pause.prompt or session.pending_user_prompt
        session.context["pending_user_input_mode"] = pause.input_mode or "text"
        session.mark(status="RUNNING", message=session.pending_user_prompt or "Waiting for user input")
        session_manager.update(session)
        await _emit_projection_updates(session)
    except Exception as exc:
        session.error = str(exc)
        session.phase = "finalize"
        session.stop_reason = "failed"
        session.mark(status="FAILED", message=session.error)
        session_manager.update(session)
        await _broadcast_task_step(session, summary=session.error, status="failed", phase="finalize")
        session.phase = "failed"
        session_manager.update(session)
        await _broadcast_event(
            session,
            event="orchestrator.session.failed",
            payload={"message": session.error, "error": session.error, "runner": session.runner, "snapshot": session.build_snapshot()},
        )
        await _broadcast_event(
            session,
            event="orchestrator.task.result",
            payload=_build_task_result_payload(
                session,
                status="failed",
                content=session.error,
                error_code=exc.__class__.__name__,
            ),
        )
        _maybe_compact_memory(session, reason="failed")
        profiles = _refresh_learning_profiles(session, reason="failed")
        await _maybe_generate_learning_pushes(session, reason="failed", profiles=profiles)
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
    _maybe_cleanup_memory(force=False)


def _maybe_cleanup_memory(*, force: bool) -> dict[str, int] | None:
    global _last_memory_cleanup_monotonic
    config = load_config()
    memory = config.memory
    if not memory.enabled or not memory.cleanup_enabled:
        return None
    now = time.monotonic()
    interval_seconds = max(1, memory.cleanup_interval_hours) * 3600
    if not force and _last_memory_cleanup_monotonic and now - _last_memory_cleanup_monotonic < interval_seconds:
        return None
    result = memory_service.cleanup()
    _last_memory_cleanup_monotonic = now
    return result


def _refresh_learning_profiles(session: OrchestratorSessionState, *, reason: str) -> dict[str, dict[str, Any]]:
    history_items = trace_store.list_session_history(session.session_id, limit=500)
    return profile_service.refresh_profiles(session=session, history_items=history_items, reason=reason)


async def _maybe_generate_learning_pushes(
    session: OrchestratorSessionState,
    *,
    reason: str,
    profiles: dict[str, dict[str, Any]],
) -> None:
    config = load_config()
    push = config.push
    if not push.enabled:
        return
    if reason == "completed" and not push.on_session_complete:
        return
    if reason == "failed" and not push.on_session_failure:
        return
    pushes = push_scheduler.generate_pushes(session=session, profiles=profiles, reason=reason)
    for push_record in pushes:
        await _broadcast_event(
            session,
            event="orchestrator.learning.push.generated",
            payload=push_record,
        )


def _is_authorized(websocket: WebSocketServerProtocol, required_token: str) -> bool:
    if not required_token:
        return True
    actual = websocket.request_headers.get("X-MetaAgent-Token", "")
    return actual == required_token


async def websocket_handler(websocket: WebSocketServerProtocol, path: str, required_token: str) -> None:
    global runner_router, memory_service, knowledge_service, learning_profile_service, profile_service, rag_service
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
            if request.type not in {"req", "request"}:
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

            if request.method == "orchestrator.task.create":
                task_text = request.params.instruction.strip() or request.params.task.strip() or request.params.goal.strip()
                session = session_manager.create(
                    task_id=request.task_id or f"task_{int(time.time() * 1000)}",
                    node_id=request.node_id or "doc_task",
                    runner=request.params.runner,
                    workspace=_ensure_workspace(request.params.workspace),
                    task=task_text,
                    goal=request.params.goal or task_text,
                )
                session.context["doc_id"] = request.params.doc_id
                _merge_request_context(session, request.params.context)
                session_manager.update(session)
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                await send_event(
                    websocket,
                    event=event_name("orchestrator.task.create"),
                    task_id=session.task_id,
                    node_id=session.node_id,
                    session_id=session.session_id,
                    payload={
                        "task_id": session.task_id,
                        "session_id": session.session_id,
                        "doc_id": request.params.doc_id,
                        "status": "pending",
                    },
                )
                session_task = asyncio.create_task(_run_session(session.session_id, websocket))
                session_tasks[session.session_id] = session_task
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
                _merge_request_context(session, request.params.context)
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                session_task = asyncio.create_task(_run_session(session.session_id, websocket))
                session_tasks[session.session_id] = session_task
                continue

            if request.method == "orchestrator.task.resume":
                target_session_id = request.session_id or request.params.session_id
                if not target_session_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "session_id is required"},
                    )
                    continue
                session = session_manager.get(target_session_id)
                if session is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=target_session_id,
                        payload={"message": "Session not found"},
                    )
                    continue
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                waiter = session_waiters.get(target_session_id)
                reply_text = request.params.input_content.strip() or request.params.text.strip()
                if waiter is not None and not waiter.done():
                    waiter.set_result(reply_text)
                elif session.awaiting_input:
                    session.context["_resume_payload"] = {
                        "kind": request.params.input_kind or "reply",
                        "content": reply_text,
                        "input_mode": request.params.input_mode or session.input_mode or "text",
                    }
                    session.context.pop("_last_awaiting_prompt_broadcast", None)
                    session_task = asyncio.create_task(_run_session(session.session_id, websocket))
                    session_tasks[session.session_id] = session_task
                else:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=session.task_id,
                        node_id=session.node_id,
                        session_id=session.session_id,
                        payload={"message": "Session is not waiting for user input"},
                    )
                    continue
                await _broadcast_event(
                    session,
                    event="orchestrator.session.followup.accepted",
                    payload={
                        "message": "Accepted user reply.",
                        "intent": request.params.input_kind or "reply",
                        "text": reply_text,
                    },
                )
                await _broadcast_task_step(session, summary="已收到补充输入，继续执行。", status="running", phase="tools")
                await _emit_projection_updates(session)
                continue

            if request.method == "orchestrator.task.interrupt":
                target_session_id = request.session_id or request.params.session_id
                if not target_session_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "session_id is required"},
                    )
                    continue
                request.session_id = target_session_id
                request.params.text = request.params.text or "Interrupt requested."
                request.method = "orchestrator.session.interrupt"

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
                update_push_config(
                    enabled=request.params.push_enabled,
                    on_session_complete=request.params.push_on_session_complete,
                    on_session_failure=request.params.push_on_session_failure,
                )
                update_langsmith_config(
                    enabled=request.params.langsmith_enabled,
                    project=request.params.langsmith_project.strip() or "pc-orchestrator-core",
                    api_key=request.params.langsmith_api_key.strip(),
                    api_url=request.params.langsmith_api_url.strip(),
                )
                update_search_config(
                    tavily_api_key=request.params.search_tavily_api_key.strip(),
                )
                # Rebuild runtime services so new planner/embedding settings apply immediately.
                reset_langsmith_tracer()
                memory_service = MemoryService()
                knowledge_service = KnowledgeBaseService()
                learning_profile_service = LearningProfileService()
                profile_service = LegacyLearningProfileService()
                runner_router = RunnerRouter()
                rag_service = RagService(knowledge_service=knowledge_service)
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

            if request.method in {"orchestrator.profile.get", "pc.profile.get"}:
                if request.params.profile_level.strip() or request.params.profile_key.strip():
                    items = []
                    if request.params.profile_level and request.params.profile_key:
                        profile = profile_service.get_profile(
                            profile_level=request.params.profile_level,
                            profile_key=request.params.profile_key,
                        )
                        if profile:
                            items.append(profile)
                    else:
                        items = profile_service.list_profiles(
                            profile_level=request.params.profile_level.strip() or None,
                            limit=max(1, request.params.limit or 50),
                        )
                    payload = {"items": items}
                else:
                    try:
                        payload = learning_profile_service.get_profile(
                            user_id=request.params.user_id,
                            layer=request.params.target.strip() or "summary",
                            course_id=request.params.course_id.strip(),
                            limit=max(1, request.params.limit or 100),
                        )
                    except Exception as exc:
                        await send_event(
                            websocket,
                            event=event_name("orchestrator.session.failed"),
                            task_id=request.task_id,
                            node_id=request.node_id,
                            session_id=request.session_id,
                            payload={"message": str(exc)},
                        )
                        continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.get"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.learning.push.list", "pc.learning.push.list"}:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.learning.push.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": push_scheduler.list_pushes(
                            session_id=request.session_id,
                            limit=max(1, request.params.limit or 50),
                        )
                    },
                )
                continue

            if request.method in {"orchestrator.tiptap.command", "pc.tiptap.command"}:
                resolved = tiptap_service.resolve(
                    command_name=request.params.command_name,
                    selection_text=request.params.selection_text,
                    document_text=request.params.document_text,
                    instruction_text=request.params.text or request.params.task,
                )
                session_to_start: OrchestratorSessionState | None = None
                payload: dict[str, Any] = {
                    **resolved.to_payload(),
                    "executed": False,
                    "mode": "preview",
                }
                if request.params.execute:
                    if request.session_id:
                        existing_session = session_manager.get(request.session_id)
                    else:
                        existing_session = None
                    if existing_session is not None and _can_accept_followup(existing_session):
                        session_manager.enqueue_followup(
                            existing_session.session_id,
                            text=resolved.task,
                            intent="instruction",
                            target=request.params.target,
                        )
                        payload.update(
                            {
                                "executed": True,
                                "mode": "followup",
                                "sessionId": existing_session.session_id,
                            }
                        )
                    else:
                        session = session_manager.create(
                            task_id=request.task_id or "tiptap-task",
                            node_id=request.node_id or "tiptap-node",
                            runner=request.params.runner,
                            workspace=_ensure_workspace(request.params.workspace),
                            task=resolved.task,
                            goal=resolved.title,
                        )
                        _subscribe(session.session_id, websocket, event_namespace)
                        subscribed_session_ids.add(session.session_id)
                        session_to_start = session
                        payload.update(
                            {
                                "executed": True,
                                "mode": "start",
                                "sessionId": session.session_id,
                            }
                        )
                        if request.session_id:
                            payload["previousSessionId"] = request.session_id
                await send_event(
                    websocket,
                    event=event_name("orchestrator.tiptap.command"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=payload.get("sessionId") or request.session_id,
                    payload=payload,
                )
                if session_to_start is not None:
                    session_task = asyncio.create_task(_run_session(session_to_start.session_id, websocket))
                    session_tasks[session_to_start.session_id] = session_task
                continue

            if request.method in {"orchestrator.profile.l1.set", "pc.profile.l1.set"}:
                try:
                    payload = learning_profile_service.upsert_l1_preferences(
                        user_id=request.params.user_id,
                        preferences=request.params.profile_data,
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.l1.set"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.profile.l2.list", "pc.profile.l2.list"}:
                payload = learning_profile_service.list_l2_contexts(
                    user_id=request.params.user_id,
                    limit=max(1, request.params.limit or 100),
                )
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.l2.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.profile.l2.upsert", "pc.profile.l2.upsert"}:
                profile_data = request.params.profile_data if isinstance(request.params.profile_data, dict) else {}
                course_id = request.params.course_id.strip() or request.params.target.strip() or str(
                    profile_data.get("courseId") or ""
                ).strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required"},
                    )
                    continue
                context = dict(profile_data)
                try:
                    payload = learning_profile_service.upsert_l2_context(
                        user_id=request.params.user_id,
                        course_id=course_id,
                        course_name=request.params.course_name.strip() or str(context.get("courseName") or "").strip(),
                        context=context,
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.l2.upsert"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.profile.l4.list", "pc.profile.l4.list"}:
                payload = learning_profile_service.list_l4_mastery(
                    user_id=request.params.user_id,
                    course_id=request.params.course_id.strip(),
                    limit=max(1, request.params.limit or 200),
                )
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.l4.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.profile.l4.upsert", "pc.profile.l4.upsert"}:
                profile_data = request.params.profile_data if isinstance(request.params.profile_data, dict) else {}
                course_id = request.params.course_id.strip() or str(profile_data.get("courseId") or "").strip()
                knowledge_point = (
                    request.params.knowledge_point.strip()
                    or request.params.target.strip()
                    or request.params.text.strip()
                    or str(profile_data.get("knowledgePoint") or "").strip()
                )
                mastery = request.params.mastery
                if mastery < 0:
                    mastery = _coerce_float(profile_data.get("mastery"), -1.0)
                if mastery < 0:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "mastery is required in params.mastery or params.profileData.mastery"},
                    )
                    continue
                confidence = request.params.confidence
                if confidence < 0:
                    confidence = _coerce_float(profile_data.get("confidence"), 0.5)
                last_practiced_at = request.params.last_practiced_at.strip() or str(
                    profile_data.get("lastPracticedAt") or ""
                ).strip()
                evidence = _coerce_str_list(profile_data.get("evidence"))
                metadata = dict(profile_data)
                metadata.pop("courseId", None)
                metadata.pop("knowledgePoint", None)
                metadata.pop("mastery", None)
                metadata.pop("confidence", None)
                metadata.pop("evidence", None)
                metadata.pop("lastPracticedAt", None)
                try:
                    payload = learning_profile_service.upsert_l4_mastery(
                        user_id=request.params.user_id,
                        course_id=course_id,
                        knowledge_point=knowledge_point,
                        mastery=float(mastery),
                        confidence=float(confidence),
                        evidence=evidence,
                        last_practiced_at=last_practiced_at,
                        metadata=metadata,
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.profile.l4.upsert"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.course.create", "pc.knowledge.course.create"}:
                course_name = request.params.course_name.strip()
                if not course_name:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseName cannot be empty"},
                    )
                    continue
                payload = knowledge_service.create_course(
                    name=course_name,
                    description=request.params.course_description.strip(),
                )
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.course.create"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.course.list", "pc.knowledge.course.list"}:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.course.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={"items": knowledge_service.list_courses(limit=max(1, request.params.limit or 50))},
                )
                continue

            if request.method in {"orchestrator.knowledge.file.ingest", "pc.knowledge.file.ingest"}:
                course_id = request.params.course_id.strip()
                file_path = request.params.file_path.strip()
                if not course_id or not file_path:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId and filePath are required"},
                    )
                    continue
                try:
                    payload = knowledge_service.ingest_file(
                        course_id=course_id,
                        file_path=file_path,
                        file_name=request.params.file_name.strip(),
                        chunk_size=max(200, request.params.chunk_size or 900),
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.file.ingest"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.file.list", "pc.knowledge.file.list"}:
                course_id = request.params.course_id.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required"},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.file.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "courseId": course_id,
                        "items": knowledge_service.list_files(course_id=course_id, limit=max(1, request.params.limit or 200)),
                    },
                )
                continue

            if request.method in {"orchestrator.knowledge.file.delete", "pc.knowledge.file.delete"}:
                course_id = request.params.course_id.strip()
                file_id = request.params.target.strip() or request.params.text.strip()
                if not course_id or not file_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId and fileId are required (fileId via params.target or params.text)"},
                    )
                    continue
                try:
                    payload = knowledge_service.delete_file(course_id=course_id, file_id=file_id)
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.file.delete"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.course.delete", "pc.knowledge.course.delete"}:
                course_id = request.params.course_id.strip() or request.params.target.strip() or request.params.text.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required (via params.courseId or params.target/params.text)"},
                    )
                    continue
                try:
                    payload = knowledge_service.delete_course(course_id=course_id)
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.course.delete"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.course.reembed", "pc.knowledge.course.reembed"}:
                course_id = request.params.course_id.strip() or request.params.target.strip() or request.params.text.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required (via params.courseId or params.target/params.text)"},
                    )
                    continue
                try:
                    payload = knowledge_service.reembed_course(
                        course_id=course_id,
                        batch_size=max(1, request.params.batch_size or 64),
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.course.reembed"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.course.reindex", "pc.knowledge.course.reindex"}:
                course_id = request.params.course_id.strip() or request.params.target.strip() or request.params.text.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required (via params.courseId or params.target/params.text)"},
                    )
                    continue
                try:
                    payload = knowledge_service.reindex_course(course_id=course_id)
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.course.reindex"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.chunk.list", "pc.knowledge.chunk.list"}:
                course_id = request.params.course_id.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required"},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.chunk.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "courseId": course_id,
                        "query": request.params.text,
                        "items": knowledge_service.list_chunks(
                            course_id=course_id,
                            limit=max(1, request.params.limit or 100),
                            query=request.params.text,
                        ),
                    },
                )
                continue

            if request.method in {"orchestrator.knowledge.rag.query", "pc.knowledge.rag.query"}:
                course_id = request.params.course_id.strip()
                question = request.params.text.strip()
                if not course_id or not question:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId and params.text are required for RAG query"},
                    )
                    continue
                try:
                    payload = await rag_service.query(
                        course_id=course_id,
                        question=question,
                        limit=max(1, request.params.limit or 8),
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.rag.query"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
                )
                continue

            if request.method in {"orchestrator.knowledge.job.list", "pc.knowledge.job.list"}:
                course_id = request.params.course_id.strip()
                if not course_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "courseId is required"},
                    )
                    continue
                try:
                    items = knowledge_service.list_jobs(
                        course_id=course_id,
                        limit=max(1, request.params.limit or 100),
                    )
                except Exception as exc:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": str(exc)},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.job.list"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={"courseId": course_id, "items": items},
                )
                continue

            if request.method in {"orchestrator.knowledge.job.get", "pc.knowledge.job.get"}:
                job_id = request.params.target.strip() or request.params.text.strip()
                if not job_id:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "jobId is required in params.target or params.text"},
                    )
                    continue
                job = knowledge_service.get_job(job_id=job_id)
                if job is None:
                    await send_event(
                        websocket,
                        event=event_name("orchestrator.session.failed"),
                        task_id=request.task_id,
                        node_id=request.node_id,
                        session_id=request.session_id,
                        payload={"message": "Knowledge job not found"},
                    )
                    continue
                await send_event(
                    websocket,
                    event=event_name("orchestrator.knowledge.job.get"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=job,
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

            if request.method in {"orchestrator.session.trace", "pc.session.trace"} and request.session_id:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.trace"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": trace_store.list_session_trace(
                            request.session_id,
                            limit=max(1, request.params.limit or 200),
                        )
                    },
                )
                continue

            if request.method in {"orchestrator.session.messages", "pc.session.messages"} and request.session_id:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.messages"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": session_manager.list_messages(
                            request.session_id,
                            limit=max(1, request.params.limit or 200),
                        )
                    },
                )
                continue

            if request.method in {"orchestrator.session.errors", "pc.session.errors"} and request.session_id:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.errors"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": session_manager.list_errors(
                            request.session_id,
                            limit=max(1, request.params.limit or 100),
                        )
                    },
                )
                continue

            if request.method in {"orchestrator.session.artifacts", "pc.session.artifacts"} and request.session_id:
                await send_event(
                    websocket,
                    event=event_name("orchestrator.session.artifacts"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload={
                        "items": session_manager.list_artifacts(
                            request.session_id,
                            limit=max(1, request.params.limit or 100),
                        ),
                        "tiles": _build_artifact_tiles(session_manager.get(request.session_id))
                        if session_manager.get(request.session_id) is not None
                        else [],
                    },
                )
                continue

            if request.method in {"orchestrator.memory.cleanup", "pc.memory.cleanup"}:
                cleanup_result = _maybe_cleanup_memory(force=True) or {
                    "deletedDocuments": 0,
                    "duplicateDocuments": 0,
                    "emptyDocuments": 0,
                }
                await send_event(
                    websocket,
                    event=event_name("orchestrator.memory.cleanup"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=cleanup_result,
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

            if request.method in {"orchestrator.memory.reindex", "pc.memory.reindex"}:
                payload = memory_service.reindex()
                await send_event(
                    websocket,
                    event=event_name("orchestrator.memory.reindex"),
                    task_id=request.task_id,
                    node_id=request.node_id,
                    session_id=request.session_id,
                    payload=payload,
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
                _subscribe(session.session_id, websocket, event_namespace)
                subscribed_session_ids.add(session.session_id)
                session.stop_reason = "interrupt_requested"
                session.latest_summary = request.params.text or "Interrupt requested."
                session.phase = "interrupting"
                session_manager.update(session)
                result = await control.interrupt()
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


