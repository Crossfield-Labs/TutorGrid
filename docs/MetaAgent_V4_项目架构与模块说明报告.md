# MetaAgent V4 项目架构与模块说明报告

> 目标读者：项目负责人、前后端协作者、后续接手的 AI/Agent、用于 Chat 迭代方案和团队分工  
> 仓库路径：`D:\SoftInnovationCompetition\Projects\pc_orchestrator_core`  
> 当前日期：2026-04-30  
> 说明：本文按当前仓库真实代码和文档现状整理，不按愿景文档想象补全。

---

## 1. 项目一句话定位

MetaAgent V4 当前是一个以 **PC 桌面/网页工作区** 为入口、以 **Python 后端 AI 编排核心** 为内核的学习型 Agent 系统。

它的核心不是单纯聊天，而是把以下能力合在一起：

- 本地工作区与磁贴文件管理
- TipTap 富文本学习文档
- WebSocket 流式 Chat
- LangGraph 编排运行时
- 多工具调用与 Worker 委派
- 课程知识库与多格式文档解析
- RAG 检索问答
- 会话记忆压缩与检索
- 学习画像与掌握度基础数据
- 主动推送的后端基础
- Harness 测试与协议回归框架

当前真实形态可以概括为：

```text
Electron/Vue/Vuetify/TipTap 前端工作区
        |
        | WebSocket: ws://127.0.0.1:3210/ws/orchestrator
        |
Python 后端 Core
  - server/protocol
  - sessions/storage
  - LangGraph runtime
  - tools/workers/runners
  - knowledge/RAG/vector
  - memory/profile/push
  - harness/tests/docs
```

---

## 2. 当前真实技术栈

### 2.1 后端技术栈

| 层级 | 当前技术 |
|---|---|
| 语言 | Python |
| 服务协议 | WebSocket，基于 `websockets` |
| 编排运行时 | LangGraph `StateGraph` |
| LLM 组织 | LangChain message/prompt 风格封装 |
| 模型 Provider | OpenAI-compatible HTTP provider，支持国产兼容 provider 别名 |
| 会话状态 | `backend/sessions` 内存态 + SQLite 投影 + JSONL trace |
| 主存储 | SQLite |
| Trace | JSONL |
| 知识库 | SQLite + `data/knowledge_bases/<course_id>/` 文件目录 |
| 向量索引 | FAISS / Chroma / JSON fallback / none |
| Embedding | OpenAI-compatible embedding 或本地 hash fallback |
| 文档解析 | python-docx、python-pptx、PyMuPDF、MinerU CLI、OCR、纯文本解析 |
| RAG | Multi-Query、HyDE、dense + lexical、rerank、answer fallback |
| Worker/CLI | Codex、OpenCode、Python runner、Shell runner；Claude 代码保留但当前禁用 |
| 配置 | `config.json` + 环境变量覆盖 |
| 测试 | unittest、harness runner、脚本式 e2e |

### 2.2 前端技术栈

当前实际前端目录是 `TutorGridFront/`，不是根 README 中提到的 `frontend/`。

| 层级 | 当前技术 |
|---|---|
| 前端框架 | Vue 3 |
| UI 框架 | Vuetify 3 |
| 桌面壳 | Electron |
| 构建工具 | Vite |
| 状态管理 | Pinia |
| 富文本编辑器 | TipTap 2 / ProseMirror |
| 拖拽 | vuedraggable |
| 图表/可视化基础 | ECharts、PlantUML 插件 |
| 本地文件访问 | Electron IPC |
| 后端通信 | Browser WebSocket |
| 测试 | Vitest，目前只有 demo 级覆盖 |

### 2.3 文档中存在的技术栈漂移

需要特别注意：

- `README.md` 当前仍写 `frontend/`，但实际前端目录是 `TutorGridFront/`。
- `README.md` 和 `harness/docs/frontend.md` 里有 React/MUI 口径，但当前真实前端是 Vue3/Vuetify3。
- `docs/前端_知识库_RAG_记忆_详细测试文档.md` 描述了独立“知识库/RAG、记忆、设置”页签，但当前实际前端路由没有这些页面。

这意味着后续分工必须以当前代码为准，而不是直接照旧文档推进。

---

## 3. 顶层目录现状

当前仓库主要目录如下：

```text
pc_orchestrator_core/
├── backend/              # Python 后端 core
├── TutorGridFront/       # 当前真实前端：Electron + Vue + Vuetify + TipTap
├── docs/                 # 人类文档、需求、协议、操作手册、报告
├── harness/              # 协议/任务驱动测试框架与模块说明
├── tests/                # Python 后端测试
├── scripts/              # e2e 脚本、启动检查、文档链接检查
├── data/                 # 知识库原始文件、课程索引等运行数据
├── scratch/              # 测试/运行产物、SQLite、trace、harness runs
├── tui/                  # TUI 客户端，当前不是主战场
├── web/                  # 历史/占位方向，不是当前主前端
├── config.json           # 本地运行配置，git 忽略
├── config.example.json   # 配置模板
├── README.md
├── AGENTS.md
└── CONTRIBUTING.md
```

### 3.1 `backend/`

这是项目核心，包含 AI 编排、协议、知识库、RAG、记忆、工具、Worker 等全部后端能力。

主要子目录：

```text
backend/
├── server/             # WebSocket 入口与协议处理
├── sessions/           # 对外 session 状态、snapshot、follow-up
├── storage/            # session/messages/errors/artifacts SQLite 投影
├── db/                 # SQLAlchemy DB model/session
├── runtime/            # LangGraph runtime、节点、路由
├── llm/                # planner、prompt、message 构造
├── providers/          # 模型 provider 抽象与 OpenAI-compatible 适配
├── tools/              # LangChain-style tools
├── workers/            # Codex/OpenCode 等 Worker 适配
├── runners/            # server 到 runtime/外部 runner 的入口抽象
├── knowledge/          # 课程知识库、文件入库、parser、chunking
├── rag/                # RAG 查询、融合、rerank、答案生成
├── vector/             # knowledge/memory 向量索引与 ranker
├── memory/             # 会话压缩、记忆文档、检索
├── learning_profile/   # L1/L2/L4 学习画像
├── profile/            # legacy profile service
├── scheduler/          # 学习推送基础服务
├── editor/             # TipTap AI 命令服务
├── observability/      # LangSmith best-effort tracing
└── dev/                # RAG 评测、benchmark、workflow 等开发脚本
```

### 3.2 `TutorGridFront/`

这是当前真实桌面前端。

主要子目录：

```text
TutorGridFront/
├── electron/           # Electron main/preload
├── src/
│   ├── views/          # 页面：BoardPage、Hyperdoc、auth、landing 等
│   ├── components/     # 通用组件、BoardCard、toolbar、navigation
│   ├── stores/         # Pinia stores
│   ├── router/         # Vue Router
│   ├── plugins/        # Vuetify/i18n/ECharts/PlantUML
│   ├── styles/         # SCSS
│   ├── types/          # Electron/window 类型
│   └── utils/
├── public/
├── dist/               # 构建产物
├── dist-electron/      # Electron 编译产物
└── package.json
```

### 3.3 `harness/`

Harness 同时承担两件事：

1. 给 agent/开发者看的模块导航文档。
2. 用 WebSocket 驱动后端执行任务并做基础评测。

主要文件：

```text
harness/
├── models.py
├── evaluator.py
├── runner.py
├── tasks/
│   └── ws_contract_smoke.json
└── docs/
    ├── README.md
    ├── server.md
    ├── runtime.md
    ├── sessions.md
    ├── knowledge.md
    ├── memory.md
    ├── workers.md
    ├── testing.md
    └── ...
```

---

## 4. 总体架构图

```text
┌──────────────────────────────────────────────────────────────┐
│                       TutorGridFront                         │
│         Electron + Vue3 + Vuetify3 + TipTap + Pinia          │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ BoardPage    │  │ HyperdocPage   │  │ ChatFAB          │  │
│  │ 磁贴工作区    │  │ TipTap 文档      │  │ 流式聊天抽屉      │  │
│  └──────┬───────┘  └───────┬────────┘  └────────┬────────┘  │
│         │                  │                    │           │
│         │ Electron IPC     │ Pinia stores        │ WebSocket │
└─────────┼──────────────────┼────────────────────┼───────────┘
          │                  │                    │
          ▼                  ▼                    ▼
┌─────────────────┐   ┌────────────────────────────────────────┐
│ Local Workspace │   │          backend/server/app.py          │
│ files, tiles    │   │       /ws/orchestrator WebSocket        │
│ hyperdocs       │   └────────────────────┬───────────────────┘
└─────────────────┘                        │
                                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Python Backend Core                       │
│                                                              │
│  protocol.py  sessions/  storage/  runtime/LangGraph         │
│       │          │          │             │                  │
│       │          │          │             ▼                  │
│       │          │          │      planning/tools/verify      │
│       │          │          │      await_user/finalize        │
│       │          │          │             │                  │
│       ▼          ▼          ▼             ▼                  │
│    config     snapshots   SQLite       tools/workers          │
│                                                              │
│  knowledge ── chunking ── embedding ── vector index           │
│       │                                      │                │
│       └────────────────── rag query ◄───────┘                │
│                                                              │
│  memory ── compaction/search ── planner context              │
│  learning_profile ── L1/L2/L4 ── push scheduler              │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 后端模块详细说明

## 5.1 Server 与协议层

主要文件：

- `backend/server/app.py`
- `backend/server/protocol.py`

职责：

- 暴露 WebSocket 服务。
- 接收前端请求。
- 解析统一 JSON frame。
- 调用 session/runtime/knowledge/memory/profile 等服务。
- 给订阅该 session 的前端广播事件。
- 把 runtime 内部状态投影成前端稳定可消费的事件和 snapshot。

WebSocket 地址：

```text
ws://127.0.0.1:3210/ws/orchestrator
```

统一请求格式：

```json
{
  "type": "req",
  "id": "request-id",
  "method": "orchestrator.xxx",
  "sessionId": "optional",
  "taskId": "optional",
  "nodeId": "optional",
  "params": {}
}
```

统一事件格式：

```json
{
  "type": "event",
  "event": "orchestrator.xxx",
  "taskId": "...",
  "nodeId": "...",
  "sessionId": "...",
  "payload": {},
  "seq": 1,
  "timestamp": "..."
}
```

当前协议层非常关键，因为前端不应该直接依赖 runtime 内部对象。前端应该只消费：

- event frame
- stable snapshot
- history / trace / messages / errors / artifacts 查询结果

### 已支持的主要请求方法

会话：

- `orchestrator.session.start`
- `orchestrator.session.list`
- `orchestrator.session.history`
- `orchestrator.session.trace`
- `orchestrator.session.messages`
- `orchestrator.session.errors`
- `orchestrator.session.artifacts`
- `orchestrator.session.input`
- `orchestrator.session.snapshot`
- `orchestrator.session.cancel`
- `orchestrator.session.interrupt`

配置：

- `orchestrator.config.get`
- `orchestrator.config.set`

编辑器：

- `orchestrator.tiptap.command`

记忆：

- `orchestrator.memory.cleanup`
- `orchestrator.memory.compact`
- `orchestrator.memory.search`
- `orchestrator.memory.reindex`

学习画像：

- `orchestrator.profile.get`
- `orchestrator.profile.l1.set`
- `orchestrator.profile.l2.list`
- `orchestrator.profile.l2.upsert`
- `orchestrator.profile.l4.list`
- `orchestrator.profile.l4.upsert`

知识库/RAG：

- `orchestrator.knowledge.course.create`
- `orchestrator.knowledge.course.list`
- `orchestrator.knowledge.course.delete`
- `orchestrator.knowledge.course.reembed`
- `orchestrator.knowledge.course.reindex`
- `orchestrator.knowledge.file.ingest`
- `orchestrator.knowledge.file.list`
- `orchestrator.knowledge.file.delete`
- `orchestrator.knowledge.chunk.list`
- `orchestrator.knowledge.job.list`
- `orchestrator.knowledge.job.get`
- `orchestrator.knowledge.rag.query`

推送：

- `orchestrator.learning.push.list`

### 已支持的主要事件

- `orchestrator.session.started`
- `orchestrator.session.progress`
- `orchestrator.session.phase`
- `orchestrator.session.worker`
- `orchestrator.session.summary`
- `orchestrator.session.message.started`
- `orchestrator.session.message.delta`
- `orchestrator.session.message.completed`
- `orchestrator.session.artifact_summary`
- `orchestrator.session.artifact.created`
- `orchestrator.session.artifact.updated`
- `orchestrator.session.artifact.removed`
- `orchestrator.session.tile`
- `orchestrator.session.permission`
- `orchestrator.session.mcp_status`
- `orchestrator.session.worker_runtime`
- `orchestrator.session.snapshot`
- `orchestrator.session.await_user`
- `orchestrator.session.completed`
- `orchestrator.session.failed`
- `orchestrator.learning.push.generated`

### 设计评价

这层目前是整个系统的“对外 API 壳”。它已经承担了很多职责，所以后续要注意：

- 新协议字段优先补 `protocol.py`。
- 新前端展示字段优先补 `session.build_snapshot()`。
- 不要让前端去读 runtime state 或 `session.context`。
- 新事件要同步更新 `docs/gui-protocol.md` 和 `harness/docs/server.md`。

---

## 5.2 Sessions 模块

主要文件：

- `backend/sessions/state.py`
- `backend/sessions/manager.py`

职责：

- 表达前端可见的 session 状态。
- 保存当前会话状态、phase、summary、worker、artifact、错误、follow-up、awaiting input。
- 构造 `snapshot`。
- 作为 runtime 与 server 之间的状态投影层。

核心类：

- `OrchestratorSessionState`
- `SessionManager`

关键设计：

```text
RuntimeState 是 LangGraph 内部状态
OrchestratorSessionState 是传输层/前端可见状态
```

这个分层很重要。前端不应该理解 LangGraph 内部状态，只看 session snapshot。

主要状态字段包括：

- `sessionId`
- `task`
- `goal`
- `runner`
- `status`
- `phase`
- `stopReason`
- `latestSummary`
- `latestArtifactSummary`
- `activeWorker`
- `activeSessionMode`
- `activeWorkerProfile`
- `activeWorkerTaskId`
- `activeWorkerCanInterrupt`
- `awaitingInput`
- `pendingUserPrompt`
- `pendingFollowups`
- `artifacts`
- `recentHookEvents`
- `errors`
- `createdAt`
- `updatedAt`

### 当前状态

Sessions 已经能支撑：

- 创建 session
- session list
- snapshot 查询
- follow-up 输入
- waiting user
- interrupt/cancel
- artifact 投影
- 错误投影

### 后续注意

`session.context` 里仍然有不少弱结构历史包袱，后续如果要做稳定 GUI 和持久恢复，应逐步把重要字段显式化。

---

## 5.3 Storage / DB 持久化模块

主要文件：

- `backend/storage/sqlite_store.py`
- `backend/storage/models.py`
- `backend/storage/jsonl_trace.py`
- `backend/db/models.py`
- `backend/db/session.py`

职责：

- 把内存 session 投影到 SQLite。
- 保存 session 列表所需字段。
- 保存 planner messages。
- 保存 errors。
- 保存 artifacts。
- 保存 snapshots。
- 追加 JSONL trace。

当前持久化模型包含：

- sessions
- session messages
- session errors
- session artifacts
- session snapshots
- JSONL trace entries

### 数据流

```text
OrchestratorSessionState
  -> build_message_rows / build_error_rows / build_artifact_rows
  -> SQLiteSessionStore
  -> scratch/storage/orchestrator.sqlite3
```

Trace：

```text
server event
  -> JsonlTraceStore
  -> scratch/session-trace/
```

### 当前状态

当前已经不是纯内存系统，GUI 所需的 session list、messages、errors、artifacts、snapshot 查询都有基础。

### 后续注意

完整历史会话恢复、checkpoint resume、trace 回放等仍有继续增强空间。

---

## 5.4 Runtime / LangGraph 编排模块

主要文件：

- `backend/runtime/runtime.py`
- `backend/runtime/graph.py`
- `backend/runtime/state.py`
- `backend/runtime/session_sync.py`
- `backend/runtime/nodes/planning.py`
- `backend/runtime/nodes/tools.py`
- `backend/runtime/nodes/await_user.py`
- `backend/runtime/nodes/verify.py`
- `backend/runtime/nodes/finalize.py`
- `backend/runtime/routes/next_step.py`
- `backend/runtime/routes/post_tools.py`

职责：

- 承载 AI 任务的真实执行图。
- 组织 planner 调用。
- 决定是否调用工具、等待用户、验证、收口。
- 把内部状态同步到 session。

当前图结构：

```text
planning
  ├── tools
  │     └── verify
  │           └── planning
  ├── await_user
  │     └── planning
  ├── verify
  │     └── planning
  └── finalize
        └── END
```

RuntimeState 包含：

- task
- goal
- workspace
- messages
- planned_tool_calls
- tool_results
- tool_events
- worker_sessions
- iteration
- max_iterations
- phase
- status
- final_answer
- stop_reason
- context

### Planning 节点能力

`planning_node` 目前已经做了不少关键逻辑：

- 消费 session follow-up
- 注入 memory search 结果
- 调用 planner
- 解析 tool calls
- 过滤重复 tool calls
- 在已有 evidence 足够时强制 finalize
- 判断是否可以直接回答
- 判断是否需要 bootstrap repo inspection
- 发送最终回答流式事件

### Tools 节点能力

`tools_node` 负责执行 planner 选择的工具，并把结果回写 runtime state。

当前工具覆盖：

- 文件列表
- 文件读取
- shell
- web fetch
- await user
- delegate task
- delegate opencode
- query database

### Await User 节点

用于 human-in-the-loop：

- planner 或工具可以触发等待用户输入。
- server 通过 `orchestrator.session.input` 接收用户回复。
- runtime 在安全点消费 follow-up 或 reply。

### 设计评价

Runtime 是当前后端的核心资产。它已经有真实 LangGraph 编排，不是一个简单函数调用链。

后续改造原则：

- 新执行阶段优先新增 node/route。
- 不要把复杂业务重新塞回 `server/app.py`。
- RuntimeState 与 SessionState 继续分层。
- 前端只看 snapshot/event，不看 RuntimeState。

---

## 5.5 LLM 与 Provider 模块

主要文件：

- `backend/llm/planner.py`
- `backend/llm/prompts.py`
- `backend/llm/messages.py`
- `backend/providers/base.py`
- `backend/providers/registry.py`
- `backend/providers/openai_compat.py`

职责：

- 组织 planner prompt。
- 维护 message 格式。
- 调用模型 provider。
- 兼容 OpenAI-compatible 接口和国产模型别名。

Provider 当前支持：

- `openai_compat`
- 常见国产 provider 名称归一到 openai-compatible：
  - qwen
  - deepseek
  - glm
  - moonshot
  - kimi
  - dashscope
  - siliconflow

配置来源：

- `config.json`
- 环境变量：
  - `ORCHESTRATOR_PROVIDER`
  - `ORCHESTRATOR_MODEL`
  - `ORCHESTRATOR_API_KEY`
  - `ORCHESTRATOR_API_BASE`
  - `ORCHESTRATOR_PROVIDER_OPTIONS_JSON`

### 设计评价

模型调用细节被隔离在 provider 层，runtime 不直接关心 HTTP。

后续如果接入国产模型，应该优先改：

- `backend/providers/registry.py`
- `backend/providers/openai_compat.py`
- `config.example.json`
- `docs/kb-rag-memory-config.md`

---

## 5.6 Tools 模块

主要文件：

- `backend/tools/registry.py`
- `backend/tools/filesystem.py`
- `backend/tools/shell.py`
- `backend/tools/web.py`
- `backend/tools/user_prompt.py`
- `backend/tools/delegate.py`
- `backend/tools/database.py`

职责：

- 给 planner/runtime 暴露可调用工具。
- 把底层操作封装为稳定工具名。
- 让 runtime 只关心工具定义和工具结果。

当前工具：

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

### 设计边界

- 文件系统工具负责读目录/读文件。
- shell 工具负责普通 shell 命令。
- user_prompt 工具负责等待用户。
- delegate 工具负责委派 Worker。
- database 工具只允许读受控表视图，不暴露任意 SQL。

### 后续注意

工具名一旦暴露给 planner 和测试，不要轻易改名。新增工具要同步测试和文档。

---

## 5.7 Workers 模块

主要文件：

- `backend/workers/base.py`
- `backend/workers/registry.py`
- `backend/workers/selection.py`
- `backend/workers/common.py`
- `backend/workers/codex_worker.py`
- `backend/workers/opencode_worker.py`
- `backend/workers/claude_worker.py`
- `backend/workers/models.py`

职责：

- 作为 runtime 委派任务的执行后端。
- 调用真实 CLI。
- 捕获 stdout/stderr。
- 计算工作区 diff。
- 回传 progress 和 artifacts。

当前可用 Worker：

- codex
- opencode

Claude 状态：

- 代码入口保留。
- 当前构建中不推荐、不启用。
- `WorkerRegistry` 主要注册 codex/opencode。

核心模型：

- `WorkerArtifact`
- `WorkerProgressEvent`
- `WorkerSessionRef`
- `WorkerControlRef`
- `WorkerResult`

### Worker 执行流程

```text
delegate_task tool
  -> select_worker
  -> WorkerRegistry.get()
  -> run_cli_worker()
  -> snapshot_workspace(before)
  -> 启动 CLI
  -> 流式收集 stdout/stderr
  -> snapshot_workspace(after)
  -> diff_workspace()
  -> WorkerResult
  -> session artifacts / summary
```

### 后续风险

真实 CLI 联调仍是风险点：

- 本机是否安装 codex/opencode
- CLI 输出格式是否变化
- 权限/交互模式是否阻塞
- 产物 diff 是否准确
- interrupt 是否真实可用

---

## 5.8 Runners 模块

主要文件：

- `backend/runners/base.py`
- `backend/runners/router.py`
- `backend/runners/subagent_runner.py`
- `backend/runners/shell_runner.py`
- `backend/runners/python_runner.py`
- `backend/runners/codex_runner.py`
- `backend/runners/opencode_runner.py`
- `backend/runners/claude_runner.py`

职责：

- 连接 server 请求和实际执行器。
- 根据 runner 名称选择执行路径。
- 保持外层入口轻量。

当前主路径：

```text
server.session.start
  -> RunnerRouter
  -> SubAgentRunner
  -> OrchestratorRuntime
  -> LangGraph
```

其他 runner：

- shell runner
- python runner
- codex runner
- opencode runner

### 设计评价

Runner 是入口适配层，不应该承担复杂编排。真正业务流转应放 runtime。

---

## 5.9 Knowledge 知识库模块

主要文件：

- `backend/knowledge/service.py`
- `backend/knowledge/store.py`
- `backend/knowledge/models.py`
- `backend/knowledge/chunking.py`
- `backend/knowledge/parsers/`

职责：

- 维护课程。
- 管理入库文件。
- 创建入库 job。
- 复制原文件到知识库目录。
- 调用 parser 提取文本块。
- chunking。
- embedding。
- 写入 SQLite。
- 重建课程向量索引。

数据目录：

```text
data/knowledge_bases/<course_id>/
├── raw/
└── index/
```

数据库表大致包括：

- knowledge_courses
- knowledge_files
- knowledge_jobs
- knowledge_chunks

### 文件入库流程

```text
orchestrator.knowledge.file.ingest
  -> KnowledgeBaseService.ingest_file()
  -> 检查 course
  -> 复制源文件到 raw/
  -> create file record
  -> create job
  -> ParserRegistry.parse_document()
  -> ChunkBuilder.chunk_document()
  -> _embed_texts()
  -> store.replace_file_chunks()
  -> vector_index.rebuild_course()
  -> 返回 chunkCount / indexBackend / embedding 信息
```

### Parser 现状

已存在：

- PlainTextParser
- DocxParser
- DocParser
- PptxParser
- PdfParser
- MinerUCliParser
- ImageOcrParser

支持格式覆盖：

- txt
- md
- doc
- docx
- ppt
- pptx
- pdf
- png/jpg/jpeg/bmp/webp

### 设计评价

Knowledge 模块是课程资料进入 AI 系统的入口。后端能力比较完整，但前端课程空间管理还不完整。

---

## 5.10 RAG 模块

主要文件：

- `backend/rag/service.py`
- `backend/rag/evaluation.py`
- `backend/vector/ranker.py`
- `backend/vector/knowledge_index.py`

职责：

- 对课程知识库做问答检索。
- 多路查询改写。
- HyDE。
- dense 检索。
- lexical/BM25 检索。
- score fusion。
- rerank。
- 生成回答。
- 提供 debug 信息和 fallback。

### RAG 查询流程

```text
question
  -> _build_multi_queries()
  -> _build_hyde_answer()
  -> dense queries
  -> knowledge_service.search_chunk_scores()
  -> lexical BM25 scores
  -> _fuse_scores()
  -> top candidates
  -> optional rerank
  -> answer generation
  -> fallback extractive answer
  -> payload: answer + items + debug
```

### 当前 RAG 特点

它不是简单关键词检索，已经有完整工程链路：

- dense + lexical
- Multi-Query
- HyDE
- rerank API / local fallback
- answer LLM / extractive fallback
- debug 字段
- evaluation utilities

### 风险

- 真实课程资料上的 Recall/MRR 仍需实测。
- OCR/PDF/PPT 解析质量会直接影响 RAG。
- Embedding fallback 适合开发，不适合正式效果评估。

---

## 5.11 Vector 模块

主要文件：

- `backend/vector/knowledge_index.py`
- `backend/vector/memory_index.py`
- `backend/vector/ranker.py`

职责：

- 为 knowledge chunks 提供持久向量索引。
- 为 memory documents 提供持久向量索引。
- 提供统一 ranker。

支持后端：

- faiss
- chroma
- json
- auto
- none

### 设计评价

JSON fallback 对比赛开发和离线演示很重要，因为不依赖 FAISS/Chroma 环境稳定性。但正式 RAG 效果最好还是配置真实 embedding 和更合适的向量后端。

---

## 5.12 Memory 模块

主要文件：

- `backend/memory/service.py`
- `backend/memory/sqlite_store.py`
- `backend/memory/compression.py`
- `backend/memory/embedding.py`
- `backend/memory/models.py`
- `backend/vector/memory_index.py`

职责：

- 把 session 历史压缩成摘要、facts、memory documents。
- 写入 SQLite。
- 建立/重建 memory vector index。
- 提供 memory search。
- 在 planning 前注入 memory context。
- 提供 cleanup。

### 记忆流程

```text
session completed/failed
  -> memory.compact
  -> SessionMemoryCompressor
  -> summary / facts / memory docs
  -> SQLiteMemoryStore
  -> MemoryVectorIndex.rebuild
```

检索：

```text
planning_node
  -> memory_service.search(query=task or goal)
  -> _build_memory_context()
  -> planner.plan(..., memory_context=...)
```

### 当前状态

已经支持：

- compact
- search
- cleanup
- reindex
- planner 注入

仍需增强：

- 合并
- 降级
- 归档
- 过期
- 与课程掌握度更深绑定

---

## 5.13 Learning Profile 学习画像模块

主要文件：

- `backend/learning_profile/service.py`
- `backend/learning_profile/store.py`

职责：

- 存储用户偏好。
- 存储课程上下文。
- 存储知识点掌握度。
- 生成画像 summary。
- 提供弱点 weak points。

当前层级：

- L1：用户偏好
- L2：课程上下文
- L4：知识点掌握度

主要接口：

- `profile.get`
- `profile.l1.set`
- `profile.l2.list`
- `profile.l2.upsert`
- `profile.l4.list`
- `profile.l4.upsert`

### 当前状态

后端数据层已经存在，前端还没有完整学习画像卡。后续可以把这个模块交给“学习画像/主动推送”方向的同学继续产品化。

---

## 5.14 Scheduler / Push 模块

主要文件：

- `backend/scheduler/service.py`
- `backend/config.py`

职责：

- 根据 session 完成/失败、学习画像、记忆等生成学习推送基础数据。
- 提供 push 配置。
- 暴露 `orchestrator.learning.push.list`。

当前状态：

- 后端基础有。
- 前端没有完整主动推送磁贴/通知气泡/生长动画。

### 后续方向

主动推送要真正成立，需要组合：

- L4 掌握度
- 课程上下文
- 最近会话
- 知识库弱点
- 前端推送卡
- 定时/触发策略

---

## 5.15 Editor / TipTap 命令模块

主要文件：

- `backend/editor/tiptap.py`

职责：

- 把前端 TipTap 的 slash command 转成后端 AI 任务。
- 支持 preview 和 execute。
- 支持新 session 和已有 session follow-up。

当前命令包括：

- explain-selection
- summarize-selection
- rewrite-selection
- continue-writing
- generate-quiz
- generate-flashcards
- ask
- do-task
- rag-query 由前端单独走 knowledge RAG

### 数据流

```text
DocumentEditor slash command
  -> orchestrator.tiptap.command
  -> TipTapAICommandService.resolve()
  -> preview payload 或 session.start/followup
  -> message stream
  -> AI block 更新
```

---

## 5.16 Observability / LangSmith

主要文件：

- `backend/observability/langsmith.py`
- `backend/config.py`

职责：

- 给 knowledge ingest、RAG、memory 等关键链路提供 best-effort tracing。
- 不阻断主流程。

配置：

- `langsmith.enabled`
- `langsmith.project`
- `langsmith.apiKey`
- `langsmith.apiUrl`

当前状态：

- 后端支持配置读写。
- 前端没有完整设置页来管理。

---

## 5.17 Config 模块

主要文件：

- `backend/config.py`
- `config.json`
- `config.example.json`

职责：

- 读取本地配置。
- 写入运行时设置。
- 支持环境变量覆盖。
- 给 planner、memory、push、LangSmith、worker、runner 提供统一配置。

主要配置域：

- planner
- memory
- push
- langsmith
- worker commands
- enabled workers
- python runner
- shell timeout

### 注意

`config.json` 已被 git 忽略，本地 API key 应放这里或环境变量中，不应提交。

---

## 5.18 Dev / Harness / Tests

### Dev 脚本

`backend/dev/` 包含：

- RAG dataset 构建
- RAG dataset 校验
- RAG 评测
- profile compare
- grid tuning
- ingest benchmark
- runtime direct run
- embedding endpoint check

### Harness

`harness/runner.py` 用 WebSocket 驱动任务并输出：

- `result.json`
- `evaluation.json`
- batch `summary.json`

当前 task：

- `harness/tasks/ws_contract_smoke.json`

### Tests

`tests/` 覆盖后端很多模块，本次实跑：

```text
Ran 118 tests in 54.812s
OK
```

测试覆盖包括：

- websocket e2e
- server protocol/input/query/artifacts/tiptap
- runtime/planning
- runner router
- worker selection/delegate
- knowledge parsers/service
- RAG service/evaluation
- vector index/ranker
- memory service/cleanup
- learning profile
- provider registry
- LangSmith config
- harness runner

---

## 6. 前端模块详细说明

## 6.1 Electron 主进程

主要文件：

- `TutorGridFront/electron/main.ts`
- `TutorGridFront/electron/preload.ts`
- `TutorGridFront/src/types/electron.d.ts`

职责：

- 创建桌面窗口。
- 区分 dev server 和 packaged file。
- 管理本地 workspace。
- 暴露安全 IPC 给 renderer。

当前 IPC 能力：

- `app:getInfo`
- `workspace:pickFolder`
- `workspace:getRoot`
- `workspace:setRoot`
- `workspace:loadTiles`
- `workspace:saveTiles`
- `workspace:importFile`
- `workspace:listRootFiles`
- `workspace:fileExists`
- `workspace:readFileBuffer`
- `workspace:readText`
- `workspace:writeText`
- `workspace:createHyperdoc`
- `workspace:deleteFile`
- `workspace:openExternal`

默认工作区：

```text
D:\SoftInnovationCompetition\TestFolder
```

工作区结构：

```text
workspaceRoot/
├── tiles.json
├── hyperdocs/
└── imported files...
```

### 设计评价

Electron 现在主要负责本地文件系统能力，不负责启动后端。后端仍需要单独启动。

---

## 6.2 Vue Router 页面结构

主要文件：

- `TutorGridFront/src/router/index.ts`
- `TutorGridFront/src/router/auth.routes.ts`
- `TutorGridFront/src/router/landing.routes.ts`

当前主要路由：

- `/` -> `/board`
- `/dashboard`
- `/board`
- `/hyperdoc/:id`
- auth routes
- landing routes
- 404

### 当前实际主页面

- `/board`：磁贴工作区
- `/hyperdoc/:id`：TipTap 文档工作区

### 当前缺失页面

没有独立：

- `/knowledge`
- `/rag`
- `/memory`
- `/settings`
- `/profile`
- `/plan-tree`

这也是前端产品化的主要缺口。

---

## 6.3 Pinia Stores

主要 store：

- `workspaceStore.ts`
- `orchestratorStore.ts`
- `knowledgeStore.ts`
- `snackbarStore.ts`
- `inspirationStore.ts`
- `customizeTheme.ts`
- `authStore.ts`
- `appStore.ts`

### workspaceStore

职责：

- 管理本地工作区 root。
- 读取/保存 `tiles.json`。
- 管理 tile 列表。
- 导入文件。
- 创建 Hyperdoc。
- 读取/写入 Hyperdoc 文本。
- 图片/PDF blob URL。
- 删除文件。
- 系统打开文件。

Tile 类型：

- note
- file
- hyperdoc

Tile source：

- file source
- hyperdoc source

### orchestratorStore

职责：

- 管理 WebSocket 连接。
- 自动重连。
- 维护 per-session subscriber。
- 缓存 session events。
- 等待某个响应事件。
- 封装后端协议调用。

已封装能力包括：

- `runTipTapCommand`
- `sessionInput`
- `knowledgeCourseList`
- `knowledgeCourseCreate`
- `knowledgeFileList`
- `knowledgeFileIngest`
- `knowledgeRagQuery`
- `fetchSessionArtifacts`
- `fetchSessionSnapshot`

它是前端和后端 core 的主连接层。

### knowledgeStore

职责：

- 管理默认课程。
- 创建/复用默认课程。
- 刷新已入库文件。
- 调用文件入库。

当前设计是“默认课程优先”，还不是完整多课程管理。

---

## 6.4 BoardPage 磁贴工作区

主要文件：

- `TutorGridFront/src/views/pages/BoardPage.vue`
- `TutorGridFront/src/components/BoardCard.vue`

当前能力：

- 列式工作区
- 新建普通磁贴
- 新建 Hyperdoc
- 导入文件
- 拖拽排序
- 编辑标题/描述
- 删除磁贴
- PDF 预览
- 图片预览
- 其他文件系统打开

BoardCard 根据文件类型显示：

- PDF
- 图片
- PPT
- Word
- Excel
- Markdown
- Text
- 其他文件
- Hyperdoc

### 当前与规格书差异

当前是 Kanban 列式磁贴，不是完整 Bento Grid：

- 没有尺寸系统
- 没有自由二维布局
- 没有 AI 生长动画
- 没有主动推送卡
- 没有思维导图卡
- 没有编排树入口卡
- 没有课程空间卡

---

## 6.5 Hyperdoc / TipTap 文档工作区

主要文件：

- `TutorGridFront/src/views/document/HyperdocPage.vue`
- `TutorGridFront/src/views/document/components/DocumentEditor.vue`
- `TutorGridFront/src/views/document/components/RichEditorMenubar.vue`
- `TutorGridFront/src/views/document/components/EditorBubbleMenu.vue`
- `TutorGridFront/src/views/document/extensions/`

职责：

- 提供 TipTap 文档编辑器。
- 支持工具栏、BubbleMenu、Slash 命令。
- 插入 AI block。
- 保存文档内容到本地 hyperdoc 文件。
- 对接后端 TipTap 命令、RAG、session stream。

AI block 类型：

- placeholder
- text
- quiz
- flashcard
- citation
- agent
- unknown

Slash 命令：

- 讲解
- 总结
- 改写
- 续写
- 出测验
- 生成闪卡
- Agent 执行任务
- 问知识库

### 当前数据流

```text
用户在 TipTap 里输入 / 命令
  -> SlashCommandMenu
  -> DocumentEditor.runAiCommand()
  -> 插入 placeholder AI block
  -> 如果是 rag-query:
       knowledgeStore.ensureDefaultCourse()
       orchestratorStore.knowledgeRagQuery()
       更新 citation/text block
     否则:
       orchestratorStore.runTipTapCommand()
       subscribeSession()
       消费 message delta / artifacts / completed
       更新 AI block
```

### 当前状态

这是前端目前最有产品特色的一块，完成度明显高于其他前端页面。

未完成：

- PDF 导出仍是占位。
- 拖拽互通不完整。
- AI/User 内容合规标记还有提升空间。
- Agent block 不是完整 Plan Tree。

---

## 6.6 ChatFAB 聊天面板

主要文件：

- `TutorGridFront/src/views/document/components/ChatFAB.vue`

职责：

- 提供 Hyperdoc 内右侧聊天抽屉。
- 连接后端 WebSocket。
- 新建或复用文档绑定 session。
- 展示流式 AI 回复。
- 支持离线 mock。

数据流：

```text
用户输入
  -> 如果文档没有 sessionId:
       runTipTapCommand(command="ask")
       保存 sessionId 到 tile metadata
     如果已有 sessionId:
       sessionInput(intent="instruction")
  -> subscribeSession(sessionId)
  -> message.started/delta/completed
  -> 更新聊天气泡
```

### 当前状态

Chat 不是全局主面板，而是 Hyperdoc 内的浮动聊天面板。流式消费已经可用。

缺口：

- 消息气泡类型体系不完整。
- 引用跳转不完整。
- 消息拖拽 Pin 到磁贴工作区未完成。

---

## 6.7 AsidePanel 知识库侧栏

主要文件：

- `TutorGridFront/src/views/document/components/AsidePanel.vue`

Tab：

- 工作区文件
- 节点详情
- 知识库

能力：

- 列出 workspace 中的 file tiles。
- 把文件加入默认知识库。
- 显示已入库文件。
- 显示 courseId。
- 展示 active agent 简要状态。

### 当前状态

这是当前知识库前端的主要入口。它实用，但不是完整知识库管理页。

缺口：

- 多课程切换
- 课程列表
- chunk/job 查看
- reembed/reindex 操作
- 删除文件/课程 UI
- RAG 调试面板

---

## 7. 关键业务链路

## 7.1 后端启动链路

```powershell
python -m backend.main --host 127.0.0.1 --port 3210
```

内部流程：

```text
backend/main.py
  -> backend/server/app.py main()
  -> run_server()
  -> websockets.serve()
  -> /ws/orchestrator
```

前端连接：

```text
orchestratorStore.connect()
  -> new WebSocket("ws://127.0.0.1:3210/ws/orchestrator")
  -> _onMessage()
  -> _dispatchEvent()
```

## 7.2 普通 AI 会话链路

```text
前端发送 orchestrator.session.start
  -> server 创建 OrchestratorSessionState
  -> RunnerRouter
  -> SubAgentRunner
  -> OrchestratorRuntime
  -> LangGraph planning
  -> planner 调 LLM
  -> 直接回答或工具调用
  -> message.started/delta/completed
  -> session.completed
  -> memory compact / push generation
```

## 7.3 TipTap 命令链路

```text
用户在文档中选择 /explain
  -> DocumentEditor 插入 placeholder block
  -> orchestrator.tiptap.command
  -> TipTapAICommandService 生成 task
  -> execute=true 时启动/复用 session
  -> 后端流式返回
  -> DocumentEditor 更新 AI block
```

## 7.4 RAG 入库链路

```text
用户在 AsidePanel 点“加入默认知识库”
  -> workspaceStore 拼出 absolutePath
  -> knowledgeStore.ingestFile()
  -> orchestrator.knowledge.file.ingest
  -> KnowledgeBaseService.ingest_file()
  -> copy raw file
  -> parser
  -> chunking
  -> embedding
  -> SQLite chunks
  -> vector index rebuild
  -> 前端刷新文件列表
```

## 7.5 RAG 查询链路

```text
用户在 TipTap 中 /rag-query
  -> knowledgeStore.ensureDefaultCourse()
  -> orchestrator.knowledge.rag.query
  -> RagService.query()
  -> multi-query
  -> HyDE
  -> dense + lexical retrieval
  -> fusion
  -> rerank
  -> answer
  -> 前端插入 citation/text AI block
```

## 7.6 Agent 委派链路

```text
planner 决定 delegate_task
  -> tools_node 执行 delegate_task
  -> worker selection
  -> Codex/OpenCode worker
  -> CLI run
  -> workspace diff
  -> artifacts
  -> session artifact events
  -> DocumentEditor agent block 更新 artifacts
```

## 7.7 记忆压缩链路

```text
session completed/failed
  -> _maybe_compact_memory()
  -> MemoryService.compact_session()
  -> SessionMemoryCompressor
  -> SQLiteMemoryStore
  -> MemoryVectorIndex.rebuild
```

## 7.8 学习画像和推送链路

```text
session 完成/失败
  -> _refresh_learning_profiles()
  -> LearningProfileService
  -> L1/L2/L4 数据更新或读取
  -> _maybe_generate_learning_pushes()
  -> LearningPushScheduler
  -> orchestrator.learning.push.generated
```

当前这条链路后端有基础，前端产品化不足。

---

## 8. 当前系统完成度体检

### 8.1 强项

后端强项：

- WebSocket 协议面完整。
- LangGraph runtime 已成型。
- Session snapshot/history/errors/artifacts 基础齐。
- RAG 工程链路较完整。
- 多格式知识库入库基础齐。
- Memory compact/search 已接 planner。
- Learning profile L1/L2/L4 已有。
- 测试覆盖较扎实。

前端强项：

- Electron 本地工作区已经可用。
- BoardPage 文件磁贴体验有基础。
- Hyperdoc + TipTap 是当前亮点。
- Slash command + AI block 已有较好原型。
- ChatFAB 已经能消费流式消息。
- RAG 局部接入已经跑到文档里。

### 8.2 主要短板

产品短板：

- 不是真正完整 Bento Grid。
- 没有完整安装向导。
- 没有独立课程空间管理。
- 没有独立知识库/RAG/记忆/设置页。
- 没有学习画像卡。
- 没有主动推送磁贴体验。
- 没有完整编排树视图。

工程短板：

- 前端自动化测试很薄。
- 前端和部分文档口径不一致。
- 后端真实 CLI/SDK 委派还需端到端验证。
- 真实课程资料 RAG 效果需验收。
- 打包态后端启动/健康检查还没形成闭环。

---

## 9. 模块分工建议

下面按适合团队分工的方式拆。

### 9.1 后端协议与编排负责人

负责范围：

- `backend/server/`
- `backend/sessions/`
- `backend/storage/`
- `backend/runtime/`
- `backend/llm/`

任务：

- 稳定 WebSocket 协议。
- 补齐 snapshot 字段。
- 维护 LangGraph 节点/路由。
- 保证 message stream、await_user、follow-up、interrupt 稳定。
- 给前端提供稳定 schema。

### 9.2 知识库/RAG 负责人

负责范围：

- `backend/knowledge/`
- `backend/rag/`
- `backend/vector/`
- `backend/dev/*rag*`
- `docs/知识库_RAG_记忆_操作手册.md`
- `docs/rag-eval-and-ingest-benchmark.md`

任务：

- 真实课程资料入库验收。
- OCR/PDF/PPT 解析优化。
- RAG profile tuning。
- 构建比赛 Demo dataset。
- 提供 RAG 引用字段给前端。

### 9.3 记忆/画像/主动推送负责人

负责范围：

- `backend/memory/`
- `backend/learning_profile/`
- `backend/scheduler/`
- 前端画像卡/推送卡

任务：

- 把 L4 掌握度和 quiz 结果打通。
- 设计主动推送策略。
- 实现学习画像 UI。
- 实现复习提醒/弱点卡。

### 9.4 前端工作区负责人

负责范围：

- `TutorGridFront/src/views/pages/BoardPage.vue`
- `TutorGridFront/src/components/BoardCard.vue`
- `TutorGridFront/src/stores/workspaceStore.ts`
- `TutorGridFront/electron/`

任务：

- 把 Kanban 磁贴升级为更接近 Bento Grid。
- 实现卡片尺寸、布局持久化、AI 生长动画。
- 完善文件导入、PDF 预览、图片/OCR入口。
- 打通打包态工作区体验。

### 9.5 TipTap/文档体验负责人

负责范围：

- `TutorGridFront/src/views/document/`
- `backend/editor/tiptap.py`

任务：

- 完善 Slash 命令。
- 完善 AI block 类型。
- 实现 PDF 导出。
- 实现 Chat/文档/磁贴拖拽互通。
- 实现 citation 跳转。

### 9.6 前端后端集成负责人

负责范围：

- `TutorGridFront/src/stores/orchestratorStore.ts`
- `TutorGridFront/src/stores/knowledgeStore.ts`
- WebSocket 协议文档

任务：

- 维护前端协议封装。
- 实现设置页。
- 实现知识库页。
- 实现记忆页。
- 实现 session history 恢复 UI。

### 9.7 测试/部署/文档负责人

负责范围：

- `tests/`
- `harness/`
- `scripts/`
- `docs/`
- GitHub Actions

任务：

- 前端核心组件测试。
- 后端 e2e/harness 场景扩展。
- 真实 Demo 脚本。
- 文档口径修正。
- Electron build 和发布包验证。

---

## 10. 推荐迭代路线

### 10.1 第一阶段：稳定可演示闭环

目标：

```text
工作区导入资料
  -> 入库知识库
  -> Hyperdoc /rag-query
  -> Chat 继续追问
  -> Agent 执行任务
  -> 文档内保留结果
```

需要补：

- 修正文档口径。
- 确保后端启动和前端连接顺滑。
- 固化默认课程入库体验。
- 准备真实课程样本。
- 优化 RAG citation 展示。

### 10.2 第二阶段：补比赛核心产品感

目标：

- 工作区不再像普通 Kanban。
- AI 主动推送有可见体验。
- 学习画像可展示。
- 编排树有入口。

需要补：

- Bento Grid 或更自由的磁贴布局。
- 主动推送卡。
- 学习画像卡。
- Agent/Plan Tree 视图。

### 10.3 第三阶段：工程化和答辩稳态

目标：

- 一键启动/安装。
- 前端核心测试。
- 后端真实样本验收。
- 演示视频脚本。

需要补：

- 安装向导。
- 设置页/API Key。
- Electron packaged flow。
- 前端测试。
- RAG evaluation report。

---

## 11. 给 Chat 迭代方案时的推荐提示词

可以把本报告和需求规格说明书一起丢给 Chat，然后这样问：

```text
你是项目技术负责人。请基于这份当前项目架构报告和需求规格说明书，
帮我们制定未来 2 周开发计划。

要求：
1. 不要假设不存在的前端页面已经有了。
2. 当前真实前端是 TutorGridFront / Vue3 / Vuetify3 / Electron / TipTap。
3. 当前后端能力较强，优先把后端能力产品化到前端。
4. 输出按人员分工、任务优先级、验收标准、风险点拆分。
5. 给出最小可演示闭环和完整比赛版本两套路线。
```

---

## 12. 最终判断

当前 MetaAgent V4 的真实项目状态是：

```text
后端 core：较成熟，具备编排、RAG、记忆、画像、协议和测试基础。
前端工作区：可运行，Hyperdoc 体验突出，但产品完整度不足。
文档体系：数量多，后端扎实，但存在前端目录/技术栈漂移。
测试体系：后端强，前端弱。
比赛风险：不是核心技术不可行，而是前端产品闭环和演示稳定性不足。
```

最合适的下一步不是重写，而是：

1. 固化现有后端协议。
2. 把前端从“雏形”推进到“完整学习工作区体验”。
3. 用真实课程资料做一条稳 Demo。
4. 同步修正文档口径和补前端测试。

这套系统的底子已经有了，接下来要把能力收束成用户一眼能懂、评委现场能看明白的产品闭环。

