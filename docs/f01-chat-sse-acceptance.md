# F01 Chat SSE 前后端验收文档

## 目标

F01 要求前后端完成 `POST /api/chat/stream` 的 Chat SSE 链路：

- 后端提供 `text/event-stream` 流式响应。
- 前端使用 `fetch` + `ReadableStream` 消费 SSE 帧。
- 支持普通 LLM 对话。
- 带 `course_id` 时触发 RAG，并在前端展示 `tool_call`、`tool_result`、`citations` 和最终回答。
- 流程以 `done` 事件结束，异常以 `error` 事件或前端错误提示呈现。

## 涉及文件

- 后端入口：`backend/http_main.py`
- 后端应用：`backend/server/http_app.py`
- Chat SSE 路由：`backend/server/chat_api.py`
- Agent 主流程：`backend/agent/main_agent.py`
- Tool 实现：`backend/agent/tools.py`
- 前端 SSE 客户端：`frontend/src/lib/chat-sse.ts`
- 前端验收界面：`frontend/src/features/chat/ChatStreamWorkbench.tsx`
- 前端入口接入：`frontend/src/app/App.tsx`

## 启动步骤

后端：

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core"
python -m uvicorn backend.http_main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core\frontend"
npm run dev:web -- --host 127.0.0.1 --port 5173
```

访问：

```text
http://127.0.0.1:5173/
```

## 普通 LLM SSE 验收

进入前端顶部 `Chat SSE` Tab：

- `Backend URL`: `http://127.0.0.1:8000`
- `Course ID`: 留空
- `Message`: `请简单介绍监督学习`
- 点击 `Send`

通过标准：

- `Events` 面板出现 `start`。
- `Answer` 区域持续追加内容。
- `Events` 面板出现多条 `delta`。
- 最终出现 `done`。
- 不出现 `当前无法调用LLM，请稍后重试。`

命令行等价验收：

```powershell
curl.exe -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/sse_f01_basic.json"
```

## RAG SSE 验收

进入前端顶部 `Chat SSE` Tab：

- `Backend URL`: `http://127.0.0.1:8000`
- `Course ID`: `f9d6020386864506b8f62dd7001a85af`
- `Message`: `observer pattern 的核心依赖关系是什么？`
- 勾选 `rag`
- 点击 `Send`

通过标准：

- `Events` 面板出现 `tool_call`，且 tool 为 `rag`。
- `Events` 面板出现 `tool_result`。
- `Citations` 面板非空。
- `Answer` 区域回答中包含 `one-to-many dependency` 或等价描述。
- 最终出现 `done`。

命令行等价验收：

```powershell
curl.exe -N -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  --data-binary "@scratch/sse_f01_rag_check.json"
```

## 构建与联调结果

已执行：

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core\frontend"
npm run build:web
```

结果：通过。

已执行：

```powershell
cd "H:\Desktop\Computer Design\pc_orchestrator_core"
python -m compileall backend\server\http_app.py
```

结果：通过。

已验证浏览器跨域预检：

```powershell
curl.exe -i -X OPTIONS "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Origin: http://127.0.0.1:5173" ^
  -H "Access-Control-Request-Method: POST" ^
  -H "Access-Control-Request-Headers: content-type"
```

结果：返回 `200 OK`，并包含 `access-control-allow-origin: http://127.0.0.1:5173`。

## 验收结论

F01 后端 SSE 与前端 Chat SSE 面板已经完成联调。普通 LLM 流、RAG 工具调用、citation 展示与 `done` 收尾均满足验收要求。
