from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from websockets.legacy.client import connect


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual WebSocket end-to-end smoke flow")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:3210/ws/orchestrator")
    parser.add_argument("--token", default="")
    parser.add_argument("--task", default="讲解一下马拉车算法")
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
        "id": f"{method}-{task_id or session_id or 'request'}",
        "method": method,
        "taskId": task_id,
        "nodeId": node_id,
        "sessionId": session_id,
        "params": params or {},
    }
    await websocket.send(json.dumps(payload, ensure_ascii=False))


async def recv_until(websocket: Any, expected_event: str, *, session_id: str | None = None) -> dict[str, Any]:
    while True:
        message = json.loads(await websocket.recv())
        if message.get("type") != "event":
            continue
        if message.get("event") != expected_event:
            print(json.dumps(message, ensure_ascii=False))
            continue
        if session_id is not None and message.get("sessionId") != session_id:
            print(json.dumps(message, ensure_ascii=False))
            continue
        print(json.dumps(message, ensure_ascii=False))
        return message


async def main_async() -> None:
    args = parse_args()
    headers = {}
    if args.token.strip():
        headers["X-MetaAgent-Token"] = args.token.strip()

    async with connect(args.ws_url, extra_headers=headers or None) as websocket:
        await send_request(
            websocket,
            "orchestrator.session.start",
            task_id="manual-task",
            node_id="manual-node",
            params={"runner": "orchestrator", "workspace": ".", "task": args.task},
        )
        started = await recv_until(websocket, "orchestrator.session.started")
        session_id = started["sessionId"]
        await recv_until(websocket, "orchestrator.session.completed", session_id=session_id)

        await send_request(websocket, "orchestrator.session.snapshot", session_id=session_id)
        await recv_until(websocket, "orchestrator.session.snapshot", session_id=session_id)

        await send_request(websocket, "orchestrator.session.history", session_id=session_id, params={"limit": 20})
        await recv_until(websocket, "orchestrator.session.history", session_id=session_id)

        await send_request(websocket, "orchestrator.memory.compact", session_id=session_id, params={"limit": 100})
        await recv_until(websocket, "orchestrator.memory.compact", session_id=session_id)

        await send_request(
            websocket,
            "orchestrator.memory.search",
            session_id=session_id,
            params={"text": args.task, "limit": 5},
        )
        await recv_until(websocket, "orchestrator.memory.search", session_id=session_id)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
