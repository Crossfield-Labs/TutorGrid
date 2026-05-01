# F02 主Agent + Tool注册表验收文档

## 目标

验证主 Agent 已接入 `/api/chat/stream`，能根据问题自动选择 RAG、Tavily，或在无 Tool 匹配时直接用 LLM 回答。

## 覆盖范围

- `backend/agent/main_agent.py`
- `backend/agent/tools.py`
- `backend/server/chat_api.py`
- `docs/agent-architecture.md`
- `tests/test_chat_agent_routing.py`

## 前置条件

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core"
pip install -r requirements.txt
uvicorn backend.http_main:app --host 0.0.0.0 --port 8000
```

如果 8000 端口已有旧服务，先停止旧进程再重启，否则不会加载最新 Agent 代码。

## 自动化验收

```powershell
python -m pytest tests\test_chat_agent_routing.py
python -m compileall backend\agent backend\server\chat_api.py backend\server\http_app.py backend\http_main.py
```

通过标准：

- `test_chat_agent_routing.py` 全部通过。
- `compileall` 无语法错误。

## 手工验收：直接 LLM 路径

创建请求文件：

```powershell
@'
{
  "session_id": "f02-direct",
  "message": "用一句话回答：你好",
  "tools": []
}
'@ | Set-Content -Encoding utf8 scratch\f02_direct.json
```

执行：

```powershell
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/f02_direct.json"
```

通过标准：

- 出现 `start`。
- 出现至少一个 `delta`。
- 出现 `done`。
- `done.metadata.tools_called` 为 `[]`。
- 不出现 `tool_call`。

## 手工验收：RAG 路径

创建请求文件：

```powershell
@'
{
  "session_id": "f02-rag",
  "message": "解释一下课程里的注意力机制",
  "course_id": "course-demo",
  "tools": ["rag", "tavily"]
}
'@ | Set-Content -Encoding utf8 scratch\f02_rag.json
```

执行：

```powershell
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/f02_rag.json"
```

通过标准：

- 出现 `tool_call`，`tool` 为 `rag`。
- 出现 `tool_result`，`tool` 为 `rag`。
- `done.metadata.tools_called` 包含 `rag_query`。
- 不应重复调用同一个预路由工具。

## 手工验收：工具 Allowlist

创建请求文件：

```powershell
@'
{
  "session_id": "f02-disable-rag",
  "message": "解释一下课程里的注意力机制",
  "course_id": "course-demo",
  "tools": ["tavily"]
}
'@ | Set-Content -Encoding utf8 scratch\f02_disable_rag.json
```

执行：

```powershell
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/f02_disable_rag.json"
```

通过标准：

- 不出现 `tool` 为 `rag` 的 `tool_call`。
- `done.metadata.tools_called` 不包含 `rag_query`。

## 文档验收

检查 `docs/agent-architecture.md`，应包含：

- Agent 结构。
- `rag_query` 和 `tavily_search` Tool 列表。
- System Prompt 模板。
- SSE 事件契约。
