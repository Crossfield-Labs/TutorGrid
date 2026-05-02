# F03 Tavily 联网搜索接入验收文档

## 目标

验证 Tavily 已作为主 Agent 的联网搜索 Tool 注册，Agent 能在最新、新闻、趋势、联网搜索类问题中自动调用 Tavily，并将带 URL 的搜索结果通过 SSE 返回给前端。

## 覆盖范围

- `backend/agent/tools.py`
- `backend/agent/main_agent.py`
- `backend/config.py`
- `frontend/src/features/chat/ChatStreamWorkbench.tsx`
- `docs/agent-architecture.md`

## 配置方式

推荐使用持久化配置：

```json
{
  "search": {
    "tavilyApiKey": "tvly-..."
  }
}
```

也可以在前端设置页填写：

```text
设置 -> Search Tools -> Tavily API Key -> 保存运行时设置
```

环境变量仍可作为部署覆盖项，优先级高于 `config.json`：

1. `TAVILY_API_KEY`
2. `ORCHESTRATOR_TAVILY_API_KEY`
3. `config.json -> search.tavilyApiKey`

如果 Tavily 未配置或请求失败，后端会退到 DuckDuckGo fallback，并在 `tool_result.warning` 中说明原因。

## 前置条件

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core"
pip install -r requirements.txt
uvicorn backend.http_main:app --host 0.0.0.0 --port 8000
```

## 自动化验收

```powershell
python -m pytest tests\test_chat_agent_routing.py tests\test_config_langsmith.py
python -m compileall backend\agent backend\server\chat_api.py backend\server\http_app.py backend\http_main.py backend\config.py backend\server\app.py backend\server\protocol.py
cd frontend
npm run build
```

通过标准：

- Python 测试全部通过。
- 后端编译无语法错误。
- 前端构建成功。

## 手工验收：Tavily 路径

创建请求文件：

```powershell
@'
{
  "session_id": "f03-tavily",
  "message": "最新的正则化方法有哪些",
  "tools": ["rag", "tavily"]
}
'@ | Set-Content -Encoding utf8 scratch\f03_tavily.json
```

执行：

```powershell
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/f03_tavily.json"
```

通过标准：

- 出现 `tool_call`，`tool` 为 `tavily`。
- 出现 `tool_result`，`tool` 为 `tavily`。
- `tool_result.results` 中包含带 `url` 的结果。
- `done.metadata.tools_called` 包含 `tavily_search`。

## 手工验收：课程问题优先 RAG

创建请求文件：

```powershell
@'
{
  "session_id": "f03-rag",
  "message": "解释一下课程里的注意力机制",
  "course_id": "course-demo",
  "tools": ["rag", "tavily"]
}
'@ | Set-Content -Encoding utf8 scratch\f03_rag.json
```

执行：

```powershell
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/f03_rag.json"
```

通过标准：

- 出现 `tool_call`，`tool` 为 `rag`。
- `done.metadata.tools_called` 包含 `rag_query`。
- 不应先出现 `tavily` 的 `tool_call`。

## 前端验收

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core\frontend"
npm run dev
```

在 Chat 页面输入：

```text
最新的正则化方法有哪些
```

通过标准：

- Answer 区流式输出。
- Events 区出现 `tavily` 的 `tool_call` 和 `tool_result`。
- Citations 区显示 Tavily 来源 URL。
