from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent import ChatAgent
from backend.chats import ChatService


router = APIRouter(prefix="/api/chat", tags=["chat"])
agent = ChatAgent()

# 由 http_app 在启动时注入（避免循环依赖）
_chat_service: ChatService | None = None


def set_chat_service(service: ChatService) -> None:
    global _chat_service
    _chat_service = service


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

    # Step 2 持久化：上来就写 user 消息 + ensure session 存在
    hyperdoc_id = (payload.context.doc_id if payload.context else "") or "_global"
    if _chat_service is not None:
        try:
            _chat_service.ensure_session(
                session_id=payload.session_id,
                hyperdoc_id=hyperdoc_id,
            )
            _chat_service.append_message(
                session_id=payload.session_id,
                role="user",
                content=payload.message,
                metadata={"origin": "chat"},
            )
        except Exception as exc:
            # 持久化失败不阻塞 SSE 流（容错）
            print(f"[chat_api] persist user message failed: {exc}")

    async def event_generator():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        # 累积 AI 完整回复 + metadata，用于流结束后写入数据库
        ai_buffer: dict[str, Any] = {
            "content": "",
            "tools_used": [],
            "citations": [],
            "search_results": [],
        }

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
                # 累积 AI 内容用于持久化
                etype = event.get("type")
                if etype == "delta":
                    ai_buffer["content"] += event.get("content", "")
                elif etype == "tool_call":
                    tool = event.get("tool")
                    if tool and tool not in ai_buffer["tools_used"]:
                        ai_buffer["tools_used"].append(tool)
                elif etype == "tool_result":
                    if event.get("citations"):
                        ai_buffer["citations"].extend(event["citations"])
                    if event.get("results"):
                        ai_buffer["search_results"].extend(event["results"])
                yield _sse_frame(event)
        finally:
            if not task.done():
                task.cancel()
            # 流结束（正常或取消）→ 写入 AI 消息（即使部分内容也存）
            if _chat_service is not None and ai_buffer["content"]:
                try:
                    _chat_service.append_message(
                        session_id=payload.session_id,
                        role="ai",
                        content=ai_buffer["content"],
                        metadata={
                            "origin": "chat",
                            "toolsUsed": ai_buffer["tools_used"],
                            "citations": ai_buffer["citations"],
                            "searchResults": ai_buffer["search_results"],
                        },
                    )
                except Exception as exc:
                    print(f"[chat_api] persist ai message failed: {exc}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
