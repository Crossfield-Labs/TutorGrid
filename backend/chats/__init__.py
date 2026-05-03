"""Chat 会话与消息持久化模块。

每个 Hyperdoc 可以有多个 ChatSession，每个 Session 有自己的消息流。
跟现有 messageStore（浏览器内存）解耦，浏览器刷新不丢历史。

跟 backend/chat_api.py（SSE 端点）配合：
- 用户发消息 → SSE 端点先写入 user message
- AI 流式完成 → SSE 端点写入 ai message（含 metadata）
"""

from backend.chats.store import ChatStore  # noqa: F401
from backend.chats.service import ChatService  # noqa: F401
