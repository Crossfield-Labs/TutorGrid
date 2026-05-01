from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent import ChatAgent


router = APIRouter(prefix="/api/chat", tags=["chat"])
agent = ChatAgent()


class ChatContext(BaseModel):
    doc_id: str = ""
    recent_paragraphs: list[str] = Field(default_factory=list)


class ChatStreamRequest(BaseModel):
    session_id: str
    message: str
    course_id: str = ""
    tools: list[str] = Field(default_factory=lambda: ["rag", "tavily"])
    context: ChatContext | None = None


def _sse_frame(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_chat(payload: ChatStreamRequest) -> StreamingResponse:
    if not payload.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    message_id = f"msg_{uuid.uuid4().hex[:10]}"

    async def event_generator():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        yield _sse_frame({"type": "start", "message_id": message_id})

        async def on_event(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def on_delta(text: str) -> None:
            await queue.put({"type": "delta", "content": text})

        async def run_agent() -> None:
            try:
                result = await agent.stream_chat(
                    message=payload.message,
                    session_id=payload.session_id,
                    course_id=payload.course_id,
                    context=payload.context.model_dump() if payload.context else None,
                    enabled_tools=payload.tools,
                    on_event=on_event,
                    on_delta=on_delta,
                )
                await queue.put(
                    {
                        "type": "done",
                        "message_id": message_id,
                        "metadata": {
                            "tools_called": result.get("tools_called", []),
                            "tokens_used": 0,
                        },
                    }
                )
            except Exception as exc:
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_agent())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse_frame(event)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
