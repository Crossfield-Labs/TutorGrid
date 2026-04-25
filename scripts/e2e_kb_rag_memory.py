from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from websockets.legacy.client import connect


EventPredicate = Callable[[dict[str, Any]], bool]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Knowledge/RAG/Memory websocket smoke test.")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:3210/ws/orchestrator")
    parser.add_argument("--token", default="")
    parser.add_argument("--timeout-sec", type=float, default=180.0)
    parser.add_argument("--course-name", default="kb-rag-memory-smoke")
    parser.add_argument("--course-description", default="kb/rag/memory smoke flow")
    parser.add_argument("--file-path", action="append", default=[], help="Repeat this arg for multiple files.")
    parser.add_argument("--query", default="Observer pattern 核心思想是什么？")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--rag-limit", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--set-langsmith", action="store_true")
    parser.add_argument("--langsmith-enabled", choices=["0", "1"], default="1")
    parser.add_argument("--langsmith-project", default="pc-orchestrator-core")
    parser.add_argument("--langsmith-api-key", default="")
    parser.add_argument("--langsmith-api-url", default="")
    return parser.parse_args()


async def send_request(
    websocket: Any,
    method: str,
    *,
    task_id: str | None = None,
    node_id: str | None = None,
    session_id: str | None = None,
    params: dict[str, Any] | None = None,
) -> None:
    payload = {
        "type": "req",
        "id": f"{method}-{uuid4().hex[:8]}",
        "method": method,
        "taskId": task_id,
        "nodeId": node_id,
        "sessionId": session_id,
        "params": params or {},
    }
    await websocket.send(json.dumps(payload, ensure_ascii=False))


def _json_brief(message: dict[str, Any]) -> str:
    event = message.get("event")
    payload = message.get("payload") or {}
    if isinstance(payload, dict):
        keys = list(payload.keys())[:8]
    else:
        keys = []
    return f"event={event}, payloadKeys={keys}"


async def recv_event(
    websocket: Any,
    expected_event: str,
    *,
    timeout_sec: float,
    predicate: EventPredicate | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Timeout waiting for event={expected_event}")
        raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        message = json.loads(raw)
        if message.get("type") != "event":
            continue
        event = message.get("event")
        if event == "orchestrator.session.failed":
            raise RuntimeError(f"Server failed: {json.dumps(message, ensure_ascii=False)}")
        if event != expected_event:
            print(f"[skip] {_json_brief(message)}")
            continue
        if predicate is not None and not predicate(message):
            print(f"[skip-predicate] {_json_brief(message)}")
            continue
        print(f"[ok] {_json_brief(message)}")
        return message


def _require_dict(data: Any, field: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected dict field: {field}")
    return data


def _find_course_id_by_name(items: list[dict[str, Any]], course_name: str) -> str:
    matches = [item for item in items if str(item.get("name") or "") == course_name]
    if not matches:
        raise RuntimeError(f"Cannot find course by name={course_name!r}")
    return str(matches[0].get("courseId") or "")


def _file_name(path: str) -> str:
    return Path(path).name or path


async def main_async() -> None:
    args = parse_args()
    headers = {}
    if args.token.strip():
        headers["X-MetaAgent-Token"] = args.token.strip()

    async with connect(args.ws_url, extra_headers=headers or None) as websocket:
        # 1) config.get
        await send_request(websocket, "orchestrator.config.get")
        config_event = await recv_event(websocket, "orchestrator.config.get", timeout_sec=args.timeout_sec)
        config_payload = _require_dict(config_event.get("payload"), "payload")
        planner = _require_dict(config_payload.get("planner"), "planner")
        memory = _require_dict(config_payload.get("memory"), "memory")
        push = _require_dict(config_payload.get("push"), "push")
        langsmith = _require_dict(config_payload.get("langsmith"), "langsmith")

        # 2) optional config.set for LangSmith
        if args.set_langsmith:
            config_set_params = {
                "provider": str(planner.get("provider") or "openai_compat"),
                "model": str(planner.get("model") or ""),
                "apiBase": str(planner.get("apiBase") or ""),
                "apiKey": str(planner.get("apiKey") or ""),
                "memoryEnabled": bool(memory.get("enabled", True)),
                "memoryAutoCompact": bool(memory.get("autoCompact", True)),
                "memoryCompactOnComplete": bool(memory.get("compactOnComplete", True)),
                "memoryCompactOnFailure": bool(memory.get("compactOnFailure", True)),
                "memoryRetrievalScope": str(memory.get("retrievalScope") or "global"),
                "memoryRetrievalStrength": str(memory.get("retrievalStrength") or "standard"),
                "memoryCleanupEnabled": bool(memory.get("cleanupEnabled", True)),
                "memoryCleanupIntervalHours": int(memory.get("cleanupIntervalHours") or 24),
                "pushEnabled": bool(push.get("enabled", True)),
                "pushOnSessionComplete": bool(push.get("onSessionComplete", True)),
                "pushOnSessionFailure": bool(push.get("onSessionFailure", False)),
                "langsmithEnabled": args.langsmith_enabled == "1",
                "langsmithProject": args.langsmith_project,
                "langsmithApiKey": args.langsmith_api_key,
                "langsmithApiUrl": args.langsmith_api_url,
            }
            await send_request(websocket, "orchestrator.config.set", params=config_set_params)
            config_set_event = await recv_event(websocket, "orchestrator.config.set", timeout_sec=args.timeout_sec)
            config_set_payload = _require_dict(config_set_event.get("payload"), "payload")
            applied = _require_dict(config_set_payload.get("langsmith"), "payload.langsmith")
            expected_enabled = args.langsmith_enabled == "1"
            if bool(applied.get("enabled")) != expected_enabled:
                raise RuntimeError("LangSmith enabled flag not applied as expected.")
            if str(applied.get("project") or "") != args.langsmith_project:
                raise RuntimeError("LangSmith project not applied as expected.")

        # 3) course.create -> course.list -> resolve courseId
        await send_request(
            websocket,
            "orchestrator.knowledge.course.create",
            params={
                "courseName": args.course_name,
                "courseDescription": args.course_description,
            },
        )
        create_event = await recv_event(websocket, "orchestrator.knowledge.course.create", timeout_sec=args.timeout_sec)
        create_payload = _require_dict(create_event.get("payload"), "payload")
        course_id = str(create_payload.get("courseId") or "")

        await send_request(websocket, "orchestrator.knowledge.course.list", params={"limit": 200})
        list_event = await recv_event(websocket, "orchestrator.knowledge.course.list", timeout_sec=args.timeout_sec)
        items = list_event.get("payload", {}).get("items") or []
        if not isinstance(items, list):
            raise RuntimeError("course.list payload.items is not a list")
        if not course_id:
            course_id = _find_course_id_by_name([item for item in items if isinstance(item, dict)], args.course_name)
        if not course_id:
            raise RuntimeError("Cannot resolve courseId after course.create/list")
        print(f"[summary] courseId={course_id}")

        # 4) optional ingest files
        ingest_results: list[dict[str, Any]] = []
        for file_path in args.file_path:
            abs_path = str(Path(file_path).expanduser().resolve())
            if not Path(abs_path).exists():
                raise FileNotFoundError(f"File not found: {abs_path}")
            await send_request(
                websocket,
                "orchestrator.knowledge.file.ingest",
                params={
                    "courseId": course_id,
                    "filePath": abs_path,
                    "fileName": _file_name(abs_path),
                    "chunkSize": max(200, int(args.chunk_size)),
                },
            )
            ingest_event = await recv_event(
                websocket,
                "orchestrator.knowledge.file.ingest",
                timeout_sec=args.timeout_sec,
                predicate=lambda msg: str(msg.get("payload", {}).get("courseId") or "") == course_id,
            )
            payload = _require_dict(ingest_event.get("payload"), "payload")
            status = str(payload.get("status") or "")
            if status != "success":
                raise RuntimeError(f"Ingest failed: {json.dumps(payload, ensure_ascii=False)}")
            ingest_results.append(payload)

        # 5) file/chunk list
        await send_request(websocket, "orchestrator.knowledge.file.list", params={"courseId": course_id, "limit": 200})
        file_list_event = await recv_event(websocket, "orchestrator.knowledge.file.list", timeout_sec=args.timeout_sec)
        file_items = file_list_event.get("payload", {}).get("items") or []
        if not isinstance(file_items, list):
            raise RuntimeError("file.list payload.items is not a list")

        await send_request(websocket, "orchestrator.knowledge.chunk.list", params={"courseId": course_id, "limit": 200})
        chunk_list_event = await recv_event(websocket, "orchestrator.knowledge.chunk.list", timeout_sec=args.timeout_sec)
        chunk_items = chunk_list_event.get("payload", {}).get("items") or []
        if not isinstance(chunk_items, list):
            raise RuntimeError("chunk.list payload.items is not a list")

        # 6) rag.query
        await send_request(
            websocket,
            "orchestrator.knowledge.rag.query",
            params={
                "courseId": course_id,
                "text": args.query,
                "limit": max(1, int(args.rag_limit)),
            },
        )
        rag_event = await recv_event(websocket, "orchestrator.knowledge.rag.query", timeout_sec=args.timeout_sec)
        rag_payload = _require_dict(rag_event.get("payload"), "payload")
        rag_items = rag_payload.get("items") or []
        if not isinstance(rag_items, list):
            raise RuntimeError("rag.query payload.items is not a list")

        # 7) reembed + reindex
        await send_request(
            websocket,
            "orchestrator.knowledge.course.reembed",
            params={"courseId": course_id, "batchSize": max(1, int(args.batch_size))},
        )
        reembed_event = await recv_event(websocket, "orchestrator.knowledge.course.reembed", timeout_sec=args.timeout_sec)
        reembed_payload = _require_dict(reembed_event.get("payload"), "payload")

        await send_request(websocket, "orchestrator.knowledge.course.reindex", params={"courseId": course_id})
        reindex_event = await recv_event(websocket, "orchestrator.knowledge.course.reindex", timeout_sec=args.timeout_sec)
        reindex_payload = _require_dict(reindex_event.get("payload"), "payload")

        # 8) memory reindex + search
        await send_request(websocket, "orchestrator.memory.reindex", params={})
        memory_reindex_event = await recv_event(websocket, "orchestrator.memory.reindex", timeout_sec=args.timeout_sec)
        memory_reindex_payload = _require_dict(memory_reindex_event.get("payload"), "payload")

        await send_request(websocket, "orchestrator.memory.search", params={"text": args.query, "limit": 5})
        memory_search_event = await recv_event(websocket, "orchestrator.memory.search", timeout_sec=args.timeout_sec)
        memory_search_payload = _require_dict(memory_search_event.get("payload"), "payload")

        summary = {
            "courseId": course_id,
            "ingestedFiles": len(ingest_results),
            "fileCount": len(file_items),
            "chunkCount": len(chunk_items),
            "ragHitCount": len(rag_items),
            "ragAnswer": str(rag_payload.get("answer") or ""),
            "ragDebug": rag_payload.get("debug") or {},
            "reembed": {
                "chunkCount": reembed_payload.get("chunkCount"),
                "updatedCount": reembed_payload.get("updatedCount"),
                "dimensions": reembed_payload.get("dimensions"),
                "indexBackend": reembed_payload.get("indexBackend"),
                "fallbackUsed": reembed_payload.get("fallbackUsed"),
            },
            "courseReindex": {
                "chunkCount": reindex_payload.get("chunkCount"),
                "dimensions": reindex_payload.get("dimensions"),
                "indexBackend": reindex_payload.get("indexBackend"),
            },
            "memoryReindex": {
                "documentCount": memory_reindex_payload.get("documentCount"),
                "dimensions": memory_reindex_payload.get("dimensions"),
                "indexBackend": memory_reindex_payload.get("indexBackend"),
            },
            "memorySearchCount": len(memory_search_payload.get("items") or []),
            "langsmithInConfig": {
                "enabled": langsmith.get("enabled"),
                "project": langsmith.get("project"),
            },
        }
        print("[final-summary]")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
