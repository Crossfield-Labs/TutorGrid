# 后端接入说明：TipTap 工作区、编排会话、知识库/RAG

> [!warning]
> 本文档部分消息已过时，应结合实际代码判断

## 1. 后端定位

当前 `./backend` 的后端是一个本地 AI 编排核心，不依赖前端实现。它主要提供：

- LangGraph 编排运行时
- WebSocket 协议入口
- TipTap 编辑器 AI 命令转译
- 会话状态、历史、trace、错误、产物查询
- 课程知识库
- 多格式文档解析
- RAG 检索问答
- 记忆压缩与检索
- 学习画像与主动推送基础能力
- worker / CLI 委派能力

推荐前端只通过 WebSocket 协议接入，不直接依赖 runtime 内部结构。

---

## 2. 启动方式

后端入口：

```powershell
python -m backend.main --host 127.0.0.1 --port 3210
```

WebSocket 地址：

```text
ws://127.0.0.1:3210/ws/orchestrator
```

统一请求格式：

```json
{
  "type": "req",
  "id": "req-001",
  "method": "orchestrator.xxx",
  "sessionId": "optional-session-id",
  "taskId": "optional-task-id",
  "nodeId": "optional-node-id",
  "params": {}
}
```

统一事件响应格式：

```json
{
  "type": "event",
  "event": "orchestrator.xxx",
  "taskId": "...",
  "nodeId": "...",
  "sessionId": "...",
  "payload": {},
  "timestamp": "..."
}
```

会话相关广播事件通常额外带 `seq`。

---

## 3. LangGraph 编排能力

运行时核心是 LangGraph 状态机：

```text
planning
  -> tools
  -> verify
  -> planning
  -> finalize

planning
  -> await_user
  -> planning

finalize
  -> END
```

当前支持的状态字段包括：

- `phase`
- `status`
- `latestSummary`
- `activeWorker`
- `awaitingInput`
- `pendingUserPrompt`
- `artifacts`
- `workerRuns`
- `toolEvents`
- `substeps`
- `finalAnswer`
- `stopReason`

主要 phase：

```text
created
planning
inspecting
delegating
verifying
awaiting_user
finalize
completed
failed
interrupting
```

planner 支持：

- 直接回答
- 调用工具
- 调用 worker 委派任务
- 等待用户输入
- 消费 follow-up
- 注入长期记忆上下文
- 重复工具调用抑制
- 最大迭代收口
- 基于已有 evidence 强制 finalize

当前工具包括：

```text
list_files
read_file
run_shell
web_fetch
await_user
delegate_task
delegate_opencode
query_database
```

---

## 4. 会话协议

### 4.1 创建会话

```json
{
  "type": "req",
  "id": "start-001",
  "method": "orchestrator.session.start",
  "params": {
    "runner": "orchestrator",
    "workspace": "D:\\your\\workspace",
    "task": "请分析这份实验文档并生成步骤计划",
    "goal": "生成可执行学习/实验计划"
  }
}
```

返回/广播事件包括：

```text
orchestrator.session.started
orchestrator.session.progress
orchestrator.session.phase
orchestrator.session.summary
orchestrator.session.message.started
orchestrator.session.message.delta
orchestrator.session.message.completed
orchestrator.session.snapshot
orchestrator.session.completed
orchestrator.session.failed
```

前端渲染聊天流时，优先消费：

```text
orchestrator.session.message.started
orchestrator.session.message.delta
orchestrator.session.message.completed
```

不要从 `summary` 或 `snapshot` 猜正文。

### 4.2 获取 snapshot

```json
{
  "type": "req",
  "id": "snapshot-001",
  "method": "orchestrator.session.snapshot",
  "sessionId": "session-id"
}
```

返回：

```json
{
  "event": "orchestrator.session.snapshot",
  "payload": {
    "snapshot": {
      "sessionId": "...",
      "task": "...",
      "goal": "...",
      "status": "RUNNING",
      "phase": "planning",
      "activeWorker": "",
      "awaitingInput": false,
      "pendingUserPrompt": "",
      "latestSummary": "...",
      "artifacts": [],
      "createdAt": "...",
      "updatedAt": "..."
    }
  }
}
```

### 4.3 用户继续输入 / 指令 / 转向

```json
{
  "type": "req",
  "id": "input-001",
  "method": "orchestrator.session.input",
  "sessionId": "session-id",
  "params": {
    "inputIntent": "instruction",
    "text": "把上面的内容改成更适合课程复习的结构",
    "target": "optional-block-id"
  }
}
```

`inputIntent` 支持：

```text
reply        等待用户输入时的直接回复
redirect     改变当前任务方向
instruction  给当前任务追加指令
comment      普通补充
explain      请求解释当前运行状态
interrupt    中断可中断 worker
```

---

## 5. TipTap 工作区后端能力

TipTap 后端入口：

```text
orchestrator.tiptap.command
```

它的作用是：把编辑器里的命令、选中文本、全文上下文翻译成一个可执行的 AI 任务。

### 5.1 支持的命令

当前内置命令：

```text
explain-selection      讲解选中内容
summarize-selection    总结选中内容
rewrite-selection      改写选中内容
continue-writing       续写当前内容
generate-quiz          生成测验题
generate-flashcards    生成记忆卡片
ask / other            通用编辑器内容处理
```

### 5.2 预览模式

只解析命令，不启动编排：

```json
{
  "type": "req",
  "id": "tiptap-preview-001",
  "method": "orchestrator.tiptap.command",
  "params": {
    "commandName": "explain-selection",
    "selectionText": "马拉车算法用于在线性时间内求最长回文子串。",
    "documentText": "",
    "text": "",
    "execute": false
  }
}
```

返回：

```json
{
  "event": "orchestrator.tiptap.command",
  "payload": {
    "commandName": "explain-selection",
    "title": "讲解选中内容",
    "task": "请讲解这段内容，突出关键概念、步骤和易错点：...",
    "selectionText": "...",
    "documentText": "...",
    "executed": false,
    "mode": "preview"
  }
}
```

### 5.3 执行模式：启动新会话

如果没有传 `sessionId`，并且 `execute=true`，后端会创建新编排会话：

```json
{
  "type": "req",
  "id": "tiptap-start-001",
  "method": "orchestrator.tiptap.command",
  "taskId": "tiptap-task-001",
  "nodeId": "editor-node-001",
  "params": {
    "runner": "orchestrator",
    "workspace": "D:\\your\\workspace",
    "commandName": "generate-quiz",
    "selectionText": "观察者模式定义对象之间的一对多依赖...",
    "documentText": "",
    "execute": true
  }
}
```

返回：

```json
{
  "payload": {
    "executed": true,
    "mode": "start",
    "sessionId": "new-session-id"
  }
}
```

随后前端继续监听该 `sessionId` 的会话事件。

### 5.4 执行模式：追加到已有会话

如果传了已有 `sessionId`，后端不会新开任务，而是把 TipTap 命令转换成 follow-up instruction：

```json
{
  "type": "req",
  "id": "tiptap-followup-001",
  "method": "orchestrator.tiptap.command",
  "sessionId": "existing-session-id",
  "params": {
    "commandName": "rewrite-selection",
    "selectionText": "原始内容",
    "text": "改成更适合教学讲义的风格",
    "target": "doc-block-123",
    "execute": true
  }
}
```

返回：

```json
{
  "payload": {
    "executed": true,
    "mode": "followup",
    "sessionId": "existing-session-id"
  }
}
```

前端应该把它理解为：当前编排会话收到了一条新的编辑器指令。

---

## 6. 知识库 / RAG 能力

知识库是课程级的。典型流程：

```text
创建课程
  -> 上传/入库文件
  -> 解析文档
  -> 切分 chunk
  -> embedding
  -> 写入 SQLite
  -> 重建课程向量索引
  -> RAG 查询
```

支持格式：

```text
.txt
.md
.pptx
.doc
.docx
.pdf
.png
.jpg
.jpeg
.bmp
.webp
```

解析策略：

- `.pptx`：python-pptx，嵌图 OCR best-effort
- `.docx`：python-docx，嵌图 OCR best-effort
- `.doc`：antiword / catdoc / LibreOffice / Word COM
- `.pdf`：MinerU / PyMuPDF / OCR fallback
- 图片：OCR
- `.txt/.md`：直接读取

向量索引支持：

```text
faiss
chroma
json
auto
none
```

默认会自动 fallback 到 JSON 索引，方便本地演示。

---

## 7. 知识库协议

### 7.1 创建课程

```json
{
  "type": "req",
  "id": "course-create-001",
  "method": "orchestrator.knowledge.course.create",
  "params": {
    "courseName": "软件设计模式",
    "courseDescription": "期末复习资料"
  }
}
```

返回：

```json
{
  "event": "orchestrator.knowledge.course.create",
  "payload": {
    "courseId": "...",
    "name": "软件设计模式",
    "description": "期末复习资料",
    "createdAt": "...",
    "updatedAt": "..."
  }
}
```

### 7.2 课程列表

```json
{
  "type": "req",
  "id": "course-list-001",
  "method": "orchestrator.knowledge.course.list",
  "params": {
    "limit": 50
  }
}
```

### 7.3 文件入库

```json
{
  "type": "req",
  "id": "file-ingest-001",
  "method": "orchestrator.knowledge.file.ingest",
  "params": {
    "courseId": "course-id",
    "filePath": "D:\\samples\\observer.md",
    "fileName": "observer.md",
    "chunkSize": 900
  }
}
```

成功返回：

```json
{
  "event": "orchestrator.knowledge.file.ingest",
  "payload": {
    "jobId": "...",
    "courseId": "...",
    "fileId": "...",
    "status": "success",
    "chunkCount": 12,
    "indexBackend": "json",
    "embeddingProvider": "hash",
    "embeddingModel": "",
    "fallbackEnabled": true,
    "fallbackUsed": false,
    "fallbackReason": ""
  }
}
```

失败返回通常是：

```text
orchestrator.session.failed
```

payload 里有 `message`。

### 7.4 文件列表

```json
{
  "type": "req",
  "id": "file-list-001",
  "method": "orchestrator.knowledge.file.list",
  "params": {
    "courseId": "course-id",
    "limit": 200
  }
}
```

### 7.5 chunk 列表

```json
{
  "type": "req",
  "id": "chunk-list-001",
  "method": "orchestrator.knowledge.chunk.list",
  "params": {
    "courseId": "course-id",
    "text": "可选过滤关键词",
    "limit": 100
  }
}
```

### 7.6 RAG 查询

```json
{
  "type": "req",
  "id": "rag-query-001",
  "method": "orchestrator.knowledge.rag.query",
  "params": {
    "courseId": "course-id",
    "text": "观察者模式的核心思想是什么？",
    "limit": 8
  }
}
```

返回：

```json
{
  "event": "orchestrator.knowledge.rag.query",
  "payload": {
    "courseId": "...",
    "query": "观察者模式的核心思想是什么？",
    "answer": "根据资料，观察者模式的核心思想是...",
    "items": [
      {
        "chunkId": "...",
        "fileId": "...",
        "content": "Observer pattern defines one-to-many dependency...",
        "sourcePage": 0,
        "sourceSection": "",
        "score": 0.82,
        "denseScore": 0.76,
        "lexicalScore": 0.91,
        "rerankScore": 0.67,
        "metadata": {}
      }
    ],
    "debug": {
      "multiQueries": ["..."],
      "hyde": "...",
      "hydeSource": "llm | question_fallback | disabled | ...",
      "hydeError": "",
      "answerSource": "llm | extractive_fallback | disabled | ...",
      "answerError": "",
      "droppedChunkCount": 0,
      "candidateCount": 12,
      "rerankMode": "local | api"
    }
  }
}
```

RAG 内部流程：

```text
原问题
  -> Multi-Query 改写
  -> HyDE 生成假想答案
  -> dense 向量检索
  -> lexical BM25 检索
  -> RRF / score fusion
  -> rerank
  -> LLM answer
  -> extractive fallback
```

### 7.7 job 查询

```json
{
  "type": "req",
  "id": "job-list-001",
  "method": "orchestrator.knowledge.job.list",
  "params": {
    "courseId": "course-id",
    "limit": 100
  }
}
```

单个 job：

```json
{
  "type": "req",
  "id": "job-get-001",
  "method": "orchestrator.knowledge.job.get",
  "params": {
    "target": "job-id"
  }
}
```

### 7.8 重嵌入与重建索引

重嵌入：

```json
{
  "type": "req",
  "id": "reembed-001",
  "method": "orchestrator.knowledge.course.reembed",
  "params": {
    "courseId": "course-id",
    "batchSize": 64
  }
}
```

重建索引：

```json
{
  "type": "req",
  "id": "reindex-001",
  "method": "orchestrator.knowledge.course.reindex",
  "params": {
    "courseId": "course-id"
  }
}
```

---

## 8. 记忆接口

### 8.1 压缩当前会话为长期记忆

```json
{
  "type": "req",
  "id": "memory-compact-001",
  "method": "orchestrator.memory.compact",
  "sessionId": "session-id",
  "params": {
    "limit": 500
  }
}
```

### 8.2 搜索记忆

```json
{
  "type": "req",
  "id": "memory-search-001",
  "method": "orchestrator.memory.search",
  "sessionId": "optional-session-id",
  "params": {
    "text": "之前讲过的观察者模式",
    "limit": 5
  }
}
```

### 8.3 整理记忆

```json
{
  "type": "req",
  "id": "memory-cleanup-001",
  "method": "orchestrator.memory.cleanup",
  "params": {}
}
```

### 8.4 重建记忆索引

```json
{
  "type": "req",
  "id": "memory-reindex-001",
  "method": "orchestrator.memory.reindex",
  "params": {}
}
```

---

## 9. 前端接入建议

### 9.1 TipTap 接入推荐流程

编辑器里用户选中文本后：

1. 调 `orchestrator.tiptap.command`，`execute=false`
2. 展示后端返回的 `title/task` 作为预览
3. 用户确认后再次调用，`execute=true`
4. 如果是新任务，不传 `sessionId`
5. 如果是对当前 AI 会话追加指令，传 `sessionId`
6. 监听返回的 `sessionId`
7. 消费该 session 的 message stream 和 snapshot

### 9.2 RAG 接入推荐流程

课程资料页：

1. `course.create`
2. `file.ingest`
3. `job.list` 或 `file.list` 展示入库状态
4. `chunk.list` 可做调试/预览
5. 用户提问时调 `rag.query`
6. 展示 `answer`
7. 展示引用 chunks：文件、页码、片段、score

### 9.3 编排会话接入推荐流程

1. `session.start`
2. 记录 `sessionId`
3. 监听：
   - `session.message.started`
   - `session.message.delta`
   - `session.message.completed`
   - `session.snapshot`
   - `session.phase`
   - `session.summary`
   - `session.completed`
   - `session.failed`
4. 用户继续说话时调 `session.input`
5. 需要恢复历史时调：
   - `session.list`
   - `session.history`
   - `session.messages`
   - `session.trace`
   - `session.errors`
   - `session.artifacts`

---

## 10. 测试方式

### 10.1 编译检查

```powershell
python -m compileall backend tests harness
```

### 10.2 LangGraph / planning 测试

```powershell
python -m unittest tests.test_planning_node tests.test_runtime_state -v
```

覆盖：

- 重复 tool call 抑制
- 已有证据时强制收口
- memory context 注入 planner
- RuntimeState 初始化

### 10.3 TipTap 测试

```powershell
python -m unittest tests.test_tiptap_service tests.test_server_tiptap -v
```

覆盖：

- TipTap 命令转任务
- `rewrite-selection` 使用 instruction
- `execute=true + sessionId` 时进入 follow-up 模式

### 10.4 Knowledge / RAG 测试

```powershell
python -m unittest tests.test_knowledge_service tests.test_rag_service tests.test_vector_knowledge_index -v
```

覆盖：

- 创建课程
- 文件入库
- chunk 持久化
- job 查询
- 删除文件/课程
- reembed
- reindex
- persistent vector index
- RAG query
- HyDE fallback
- answer fallback

### 10.5 RAG 评测脚本

```powershell
python -m backend.dev.evaluate_rag --dataset docs/examples/rag_eval_dataset.json
python -m backend.dev.compare_rag_profiles --dataset docs/examples/rag_eval_dataset.json
python -m backend.dev.tune_rag_grid --dataset docs/examples/rag_eval_dataset.json
python -m backend.dev.run_rag_workflow --dataset docs/examples/rag_eval_dataset.json
```

评测指标：

```text
Recall@K
MRR
latency
profile 对比
chunk size 网格调参
推荐配置报告
```

---

## 11. 重要环境变量

Embedding：

```powershell
$env:ORCHESTRATOR_EMBEDDING_PROVIDER="openai_compat"
$env:ORCHESTRATOR_EMBEDDING_API_BASE="..."
$env:ORCHESTRATOR_EMBEDDING_API_KEY="..."
$env:ORCHESTRATOR_EMBEDDING_MODEL="text-embedding-3-large"
$env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED="1"
```

知识库索引：

```powershell
$env:ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND="auto"
# 可选：faiss / chroma / json / none
```

RAG：

```powershell
$env:ORCHESTRATOR_RAG_MULTI_QUERY="1"
$env:ORCHESTRATOR_RAG_HYDE="1"
$env:ORCHESTRATOR_RAG_RERANK="1"
$env:ORCHESTRATOR_RAG_ANSWER_ENABLED="1"
```

PDF / OCR / DOC：

```powershell
$env:ORCHESTRATOR_PDF_PARSE_STRATEGY="auto"
$env:ORCHESTRATOR_MINERU_ENABLED="1"
$env:ORCHESTRATOR_PDF_OCR_FALLBACK="1"
$env:ORCHESTRATOR_DOC_SOFFICE_BINARY="C:\\Program Files\\LibreOffice\\program\\soffice.exe"
```

---

## 12. 当前边界和注意点

1. 前端不要直接依赖 `session.context`。
2. 前端不要直接读取 runtime graph state。
3. 前端应只消费 WebSocket event 和 snapshot。
4. TipTap 后端现在负责“命令转任务”，不负责保存 TipTap 文档本身。
5. RAG 入库现在是同步流程，大文件可能耗时，建议 UI 上显示处理中状态。
6. embedding 默认允许 hash fallback，适合开发演示；正式验收建议关闭 fallback。
7. 真实 PDF/OCR/MinerU/DOC 解析能力依赖本机环境。
8. 当前 LangGraph 已用于编排，但 checkpoint/resume 还不是完整原生 LangGraph checkpoint 体系。
9. RAG 已有完整工程链路，但还需要用真实课程资料做系统验收。
```

这版是按当前后端实际代码整理的，另一个 AI 可以直接按这里的 WebSocket 方法和 payload 设计接入层。