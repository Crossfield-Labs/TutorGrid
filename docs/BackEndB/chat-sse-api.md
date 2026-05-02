# Chat SSE API

## Endpoint

- Method: `POST`
- Path: `/api/chat/stream`
- Response content type: `text/event-stream`

## Request

```json
{
  "session_id": "sess_xxx",
  "message": "请简单介绍监督学习",
  "course_id": "f9d6020386864506b8f62dd7001a85af",
  "tools": ["rag", "tavily"],
  "context": {
    "doc_id": "hyper_001",
    "recent_paragraphs": ["用户最近写入文档的段落"]
  }
}
```

Fields:

- `session_id`: Required. Frontend session identifier.
- `message`: Required. User message.
- `course_id`: Optional. When present, the agent can use RAG for course-specific answers.
- `tools`: Optional. Supported values include `rag` and `tavily`.
- `context`: Optional. Document-side context for Copilot-style scenarios.

## SSE Events

Each event is emitted as a standard SSE data frame:

```text
data: {"type":"delta","content":"..."}
```

Supported event types:

- `start`: stream started.
- `tool_call`: agent is invoking a tool.
- `tool_result`: tool returned summary data, such as RAG citations.
- `delta`: answer token/content delta.
- `done`: stream completed.
- `error`: stream failed.

## Example Flow

Plain LLM chat:

```text
data: {"type":"start","message_id":"msg_xxx"}

data: {"type":"delta","content":"监督"}

data: {"type":"delta","content":"学习"}

data: {"type":"done","message_id":"msg_xxx","metadata":{"tools_called":[],"tokens_used":0}}
```

RAG chat:

```text
data: {"type":"start","message_id":"msg_xxx"}

data: {"type":"tool_call","tool":"rag","query":"observer pattern 的核心依赖关系是什么？"}

data: {"type":"tool_result","tool":"rag","citations":[{"source":"...","page":0,"chunk":"Observer pattern defines one-to-many dependency.","score":0.56}]}

data: {"type":"delta","content":"根据提供的上下文，Observer pattern 的核心依赖关系是 one-to-many dependency。"}

data: {"type":"done","message_id":"msg_xxx","metadata":{"tools_called":["rag_query"],"tokens_used":0}}
```

## Frontend Integration

The frontend consumes this endpoint through:

- `frontend/src/lib/chat-sse.ts`
- `frontend/src/features/chat/ChatStreamWorkbench.tsx`

The implementation uses `fetch`, reads `response.body.getReader()`, splits SSE frames by blank lines, parses `data:` JSON payloads, appends `delta` content, and renders `tool_result.citations`.
