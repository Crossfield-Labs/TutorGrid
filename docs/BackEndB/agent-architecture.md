# F02/F03 Agent Architecture

## Scope

F02 implements the main chat Agent and tool registry used by `POST /api/chat/stream`.

F03 completes Tavily web search integration as a first-class Agent tool. The Agent can decide to search the web without the frontend explicitly triggering a search-only endpoint.

The Agent behaves as a student Copilot: it helps students understand, organize, and verify knowledge, but does not replace learning.

## Runtime Flow

1. Frontend posts a chat request to `POST /api/chat/stream`.
2. `backend/server/chat_api.py` validates the request and opens an SSE stream.
3. `backend/agent/main_agent.py` builds the system prompt, user message, and available tool list.
4. The Agent applies deterministic pre-routing for high-confidence cases:
   - Course-scoped non-time-sensitive questions use RAG first.
   - Time-sensitive or web-search questions use Tavily first.
   - General questions go directly to the LLM.
5. The Agent also passes OpenAI-compatible tool definitions to the LLM so the model can request tools when deterministic routing does not catch a case.
6. Tool progress is emitted as SSE events before final streamed text.
7. The final answer is streamed as `delta` events and closed by a `done` event.

## Files

- `backend/agent/main_agent.py`: Agent orchestration, prompt construction, routing, tool-call loop, SSE event integration.
- `backend/agent/tools.py`: Tool schema registry and tool execution functions.
- `backend/server/chat_api.py`: HTTP/SSE adapter for the Agent.
- `backend/rag/service.py`: Course knowledge retrieval service used by `rag_query`.
- `backend/config.py`: Persistent Tavily key config at `search.tavilyApiKey`.
- `frontend/src/features/chat/ChatStreamWorkbench.tsx`: Chat SSE workbench that renders streamed text, RAG citations, and Tavily URL results.

## System Prompt Template

```text
你是学生的 Copilot 副驾驶，目标是帮助理解和整理知识，而不是替代学习。
回答要准确、简洁、可执行；当信息不充分时要明确说明。
如果是课程知识问题，优先使用 rag_query。
如果是时效性问题（最新、近期、新闻、政策更新、趋势），优先使用 tavily_search。
引用工具结果时要说明依据，不要编造来源。
```

When `course_id` or document context exists, the Agent appends them to the system prompt as grounded conversation context.

## Tool Registry

### `rag_query`

Purpose: retrieve course knowledge and citations.

Input:

```json
{
  "question": "string",
  "course_id": "string"
}
```

Output:

```json
{
  "answer": "string",
  "citations": [
    {
      "source": "string",
      "page": 0,
      "chunk": "string",
      "score": 0.0
    }
  ],
  "raw": {}
}
```

Routing rule: used first when `course_id` is present and the user question is not time-sensitive.

### `tavily_search`

Purpose: search the web for fresh information and return source URLs.

Input:

```json
{
  "query": "string",
  "max_results": 5
}
```

Output:

```json
{
  "answer": "string",
  "results": [
    {
      "title": "string",
      "url": "string",
      "content": "string",
      "score": 0.0
    }
  ],
  "warning": "string",
  "fallback": "string",
  "raw": {}
}
```

Routing rule: used first when the user asks time-sensitive or web-search questions containing terms such as `最新`, `最近`, `今天`, `新闻`, `更新`, `趋势`, `联网`, `搜索`, `查一下`, `搜一下`, `latest`, `current`, `news`, `search`, or `web`.

Configuration:

```json
{
  "search": {
    "tavilyApiKey": "tvly-..."
  }
}
```

Environment override order:

1. `TAVILY_API_KEY`
2. `ORCHESTRATOR_TAVILY_API_KEY`
3. `config.json -> search.tavilyApiKey`

If Tavily is not configured or the Tavily HTTP request fails, the tool falls back to DuckDuckGo Instant Answer and includes a `warning` field. This keeps local demos observable even when Tavily quota or credentials are unavailable.

## Enabled Tools

The request payload can restrict available tools:

```json
{
  "tools": ["rag", "tavily"]
}
```

The same allowlist is applied to deterministic pre-routing and LLM-visible tool schemas. For example, `tools: ["rag"]` prevents Tavily prefetch and hides `tavily_search` from the model.

## SSE Event Contract

Typical RAG path:

```text
data: {"type":"start","message_id":"msg_xxx"}

data: {"type":"tool_call","tool":"rag","query":"..."}

data: {"type":"tool_result","tool":"rag","citations":[...]}

data: {"type":"delta","content":"..."}

data: {"type":"done","message_id":"msg_xxx","metadata":{"tools_called":["rag_query"],"tokens_used":0}}
```

Typical Tavily path:

```text
data: {"type":"start","message_id":"msg_xxx"}

data: {"type":"tool_call","tool":"tavily","query":"最新的正则化方法有哪些"}

data: {"type":"tool_result","tool":"tavily","results":[{"title":"...","url":"https://...","content":"...","score":0.9}]}

data: {"type":"delta","content":"..."}

data: {"type":"done","message_id":"msg_xxx","metadata":{"tools_called":["tavily_search"],"tokens_used":0}}
```

Typical direct LLM path:

```text
data: {"type":"start","message_id":"msg_xxx"}

data: {"type":"delta","content":"..."}

data: {"type":"done","message_id":"msg_xxx","metadata":{"tools_called":[],"tokens_used":0}}
```

## F03 Acceptance Focus

- Asking `最新的正则化方法有哪些` should emit `tool_call` with `tool: "tavily"` and `done.metadata.tools_called` containing `tavily_search`.
- Tavily `tool_result` should include `results` items with non-empty `url` fields when Tavily or fallback search returns sources.
- Asking a course-scoped knowledge question should emit `tool_call` with `tool: "rag"` and should not call Tavily first.
- If no tool matches, the Agent should stream a direct LLM answer with an empty `tools_called` list.

## Local Verification

```powershell
python -m pytest tests\test_chat_agent_routing.py tests\test_config_langsmith.py
python -m compileall backend\agent backend\server\chat_api.py backend\server\http_app.py backend\http_main.py backend\config.py backend\server\app.py backend\server\protocol.py
cd frontend
npm run build
```