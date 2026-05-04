# 编排引擎架构讲解（写给前端 A · 波，）

> 作用：把后端 A · 贤这几天 F04 + F05 重构的东西**用人话**讲一遍。
> 不是协议规范，不是验收清单，是"老朋友坐你旁边给你讲他写了啥"。
>
> 配套文档：
> - 协议规范（要查字段名）：[orchestrator-v5-protocol.md](./orchestrator-v5-protocol.md)
> - Worker 选型规则：[worker-delegation.md](./worker-delegation.md)
> - 怎么测：[F04-F05-验收指南.md](./F04-F05-验收指南.md)

---

## 0 · 一句话总结

> 他写的是一个**任务调度器**：用户在 hyperdoc 文档里输入"帮我跑线性回归"，这句话经过 WebSocket 进入 LangGraph 的 5 节点状态图，沿着 "规划 → 调工具 → 验证 → 整理" 走一遍，过程中可能委派给 Python 沙盒 / Codex CLI / OpenCode CLI 干活，每一步都实时推回前端磁贴显示进度。失败会兜底，不会崩。

---

## 1 · 整体架构（画个图理解）

```
┌──────────── Electron 桌面壳 ────────────┐
│  Vue3 前端                                │
│  ┌────────────────────────────────────┐  │
│  │ HyperdocPage.vue                    │  │
│  │   → TileGrid (磁贴网格)              │  │
│  │     → TaskTile.vue ★ 编排磁贴        │  │
│  │       [新建任务] [中断] [查看详情]    │  │
│  │                                      │  │
│  │ /tasks/:id → TaskDetailsPage.vue    │  │
│  └─────┬──────────────────────────┬───┘  │
│        │                          │       │
│   orchestratorTaskStore (Pinia) ──┘       │
│        │ ↑                                 │
│        │ │ 订阅事件并更新 UI               │
│        ↓ │                                 │
│   orchestratorStore (底层 ws 连接)         │
└────────┼─────────────────────────────────┘
         │
         │  WebSocket /ws/orchestrator
         │  (Electron 启动时自动 spawn 后端)
         ↓
┌────────────────────────────────────────────┐
│  Python 后端进程 #2 — port 3210             │
│  backend/server/app.py                      │
│   ↓ 接收 task.create                        │
│  backend/sessions/manager.py                │
│   ↓ 创建 OrchestratorSessionState           │
│  backend/runtime/runtime.py                 │
│   ↓ 启动 LangGraph                          │
│                                              │
│  ┌──── LangGraph 5 节点状态图 ────┐         │
│  │                                  │         │
│  │   planning ─┬→ tools ─┬→ verify │         │
│  │      ↑      │   ↑     │   │     │         │
│  │      │      │   │     │   ↓     │         │
│  │      │      │   └─ await_user   │         │
│  │      │      │                    │         │
│  │      │      └→ finalize → END   │         │
│  │      │              ↑           │         │
│  │      └──────────────┘           │         │
│  │  (verify/await_user 都回 planning) │       │
│  └──────────────────────────────────┘         │
│                  │                             │
│   tools 节点会调：                              │
│   • backend/tools/delegate.py                  │
│     ↓ 选 worker                                 │
│   • backend/workers/selection.py               │
│     ↓ 路由                                     │
│   ┌────────────┬─────────────┬──────────┐    │
│   │python_runner│ codex CLI  │opencode  │    │
│   │ (本地 Python │ (审查/分析) │(实现/修改)│    │
│   │  沙盒+sklearn│             │          │    │
│   │  demo 兜底) │             │          │    │
│   └────────────┴─────────────┴──────────┘    │
│   全挂 → fallback worker (纯 LLM 推理，不崩)  │
└────────────────────────────────────────────┘

(同时还有 #1 进程：HTTP 后端 port 8000，
 跑 chat / RAG / 配置等，与编排无关)
```

**两个端口分工，一定要分清**：
| 端口 | 进程 | 协议 | 干啥 |
|---|---|---|---|
| 8000 | uvicorn `backend.server.http_app` | HTTP | F01-F03 / F13 那些 REST 接口 |
| 3210 | `backend.server.app` | WebSocket | **本次 F04/F05 主角**，编排任务 |

---

## 2 · 调用链：你点磁贴上"新建任务"会发生什么

按时间顺序把整条链跟一遍，每一步都标了文件和行号，你能拿着这条链路走查任何 bug。

```
[用户操作]
你在文档右侧 TaskTile 磁贴上点"新建任务"
   ↓
[前端 Step 1] TaskTile.vue:382 openStartFlow()
   弹出输入框对话框
   ↓
[前端 Step 2] TaskTile.vue:390 submitStart()
   emit('start', "用 sklearn 跑线性回归")
   ↓
[前端 Step 3] HyperdocPage.vue（监听 @start）
   调 orchestratorTaskStore.createTask({docId, instruction})
   ↓
[前端 Step 4] orchestratorTaskStore.ts:199 createTask()
   → orchestratorStore.connect()（建立 ws 连接）
   → orchestratorStore.createTask({...}) 发出帧:
     {
       type: "request",
       method: "orchestrator.task.create",
       params: { sessionId, docId, instruction }
     }
   ↓
══════════ WebSocket /ws/orchestrator 跨进程 ══════════
   ↓
[后端 Step 5] backend/server/app.py:1041
   匹配到 method == "orchestrator.task.create"
   ↓
[后端 Step 6] app.py:1043-1058
   - 生成 task_id = "task_<时间戳>"
   - _ensure_task_workspace(...) 在 scratch/tasks/<task_id>/ 建工作目录
   - session_manager.create(...) 建 OrchestratorSessionState 对象
   - session.context["doc_id"] = doc_id
   ↓
[后端 Step 7] app.py:1061 立即回复一个事件给前端
   event: "orchestrator.task.create"
   payload: {task_id, session_id, doc_id, status: "pending"}
   ↓ 前端收到这条事件就把磁贴标成"已创建"
[后端 Step 8] app.py:1074 起一个后台 task
   asyncio.create_task(_run_session(session_id, websocket))
   ↓
[后端 Step 9] _run_session() 调 runner_router.get(session.runner)
   编排任务用 "orchestrator" runner，最终走到
   ↓
[后端 Step 10] backend/runtime/runtime.py:OrchestratorRuntime.run()
   - build_runtime_graph(): LangGraph 5 节点状态图编译好
   - 把 session 状态投影成 RuntimeState
   - graph.astream(...) 流式跑
   ↓
[后端 Step 11] LangGraph 节点逐个执行
   planning  → backend/runtime/nodes/planning.py
              (调 LLM 规划，决定下一步去哪)
   tools     → backend/runtime/nodes/tools.py
              (执行工具调用，可能委派给 worker)
   verify    → backend/runtime/nodes/verify.py
              (检查结果，需要补步骤就跳回 planning)
   finalize  → backend/runtime/nodes/finalize.py
              (整理最终输出)

   每个节点跑完都回调 emit_progress(...)
   emit_progress 内部又调 _broadcast_task_step()
   把 4 步进度广播给前端
   ↓
[后端 Step 12] tools 节点如果遇到代码执行需求
   → backend/tools/delegate.py:155 delegate()
   → backend/workers/selection.py:select_worker()
     按关键词路由：含 "python/sklearn" → python_runner
                  含 "review" → codex
                  含 "implement" → opencode
                  默认 opencode → 失败 fallback codex
   → 选中的 worker run()
     • python_runner: backend/runners/python_runner.py
       在 scratch/tasks/<task_id>/ 跑 Python，
       生成的 png 自动登记到 session.artifacts
     • codex_runner / opencode_runner: spawn CLI 子进程
   → 全部失败时 delegate.py:239 兜底返回:
     {worker:"fallback", metadata:{fallback_recommended:True}}
   ↓
[后端 Step 13] 节点之间状态变化时不断推 task.step 事件
   每个事件 payload 含:
     phase, status, step_index/total, summary,
     active_worker (当前在干活的 worker 名字)
   ↓
[后端 Step 14] graph 走到 finalize → END
   _run_session 拿到最终 result，调 _broadcast_task_result_payload()
   推一条 event: "orchestrator.task.result"
   payload: {status:"done", content, artifacts, worker_runs}
   ↓
══════════ WebSocket 推回前端 ══════════
   ↓
[前端 Step 15] orchestratorTaskStore.ts:107 _ensureSessionSubscription()
   注册的回调收到事件:
   - task.step → 更新磁贴的 4 步进度条
   - task.awaiting_user → 磁贴变黄"等待补充输入"
   - task.result → 磁贴显示"编排已完成"，artifacts 进 store
   ↓
[前端 Step 16] TaskTile.vue 响应式重渲染
   你看到磁贴 4 步进度条变绿，点"查看详情"跳到 /tasks/:id
   能看到产物 PNG / worker 列表 / 完整 step 详情
```

**这条链你看明白了，整个系统就懂了。**任何 bug 顺着对应的 Step 去找文件就行。

---

## 3 · 后端文件分组讲解

后端 A · 贤这几天 **改了 23 个文件，新增 1571 行，删 55 行**（仅 F04/F05 那段，F01-F03 不算）。按职责分 5 组讲。

### 3.1 协议层（前端怎么跟后端说话）

| 文件 | 干啥的 | 关键点 |
|---|---|---|
| [backend/server/app.py](../../backend/server/app.py) | **WebSocket 主入口**。一个超长 dispatch，按 `request.method` 分发 | 1041 行 task.create / 1097 行 task.resume / 1158 行 task.interrupt。同时负责把 session 内部事件**翻译**成 task.* 协议事件（`_broadcast_task_step` 192 行 / `_build_task_result_payload` 255 行） |
| [backend/server/protocol.py](../../backend/server/protocol.py) | 帧格式 dataclass | `OrchestratorRequest.from_dict` 解析 camelCase；`build_event` 输出帧。这层**做了大量字段名兼容**（camelCase / snake_case 都收） |
| [backend/server/http_app.py](../../backend/server/http_app.py) | HTTP 后端（port 8000）入口 | 跟编排没关系，但他这次也改了一些 |

**亮点**：贤把"新协议（task.\*）"做成**对旧协议（session.\*）的投影层**，旧 GUI 调试协议没删，新前端只用 task.\*。这个分层很干净，不破坏老测试。

**坑**：app.py 1300+ 行，太长了，分发逻辑没拆。但这是答辩前不该动的事。

### 3.2 状态层（任务在内存里长什么样）

| 文件 | 干啥的 | 关键点 |
|---|---|---|
| [backend/sessions/state.py](../../backend/sessions/state.py) | `OrchestratorSessionState` dataclass | 47 个字段：task_id / phase / status / artifacts / worker_runs / awaiting_input / pending_user_prompt … 这就是任务在内存里的全部"户口" |
| [backend/sessions/manager.py](../../backend/sessions/manager.py) | session 增删查改，内存级 | 没持久化（没存 SQLite），重启就丢；F10/F11 是 chat 持久化，编排任务暂时不持久 |

**关键概念**：`session_id` 不等于 `task_id`。一个 session 是一段编排会话，task 是这段会话中**当前**承载的任务。但 V5 之后基本是 1:1 关系，前端可以视作同一个东西。

### 3.3 运行时层（4 步状态图怎么跑）

这是 **F04 的核心**。

| 文件 | 干啥的 |
|---|---|
| [backend/runtime/graph.py](../../backend/runtime/graph.py) | **LangGraph 装配**。5 节点：planning / tools / await_user / verify / finalize。条件边路由 |
| [backend/runtime/runtime.py](../../backend/runtime/runtime.py) | `OrchestratorRuntime` 类，把 session → RuntimeState，跑 graph，收回 result |
| [backend/runtime/state.py](../../backend/runtime/state.py) | RuntimeState dataclass（LangGraph 节点之间传的状态） |
| [backend/runtime/nodes/planning.py](../../backend/runtime/nodes/planning.py) | **规划节点**：调 LLM，让它决定下一步是"调工具""问用户""验证""结束" |
| [backend/runtime/nodes/tools.py](../../backend/runtime/nodes/tools.py) | **工具节点**：执行 LLM 选好的工具调用。**这里有 worker 委派的钩子** |
| [backend/runtime/nodes/await_user.py](../../backend/runtime/nodes/await_user.py) | **询问用户节点**：抛 `RuntimePaused` 异常暂停 graph，等 resume |
| [backend/runtime/nodes/verify.py](../../backend/runtime/nodes/verify.py) | **验证节点**：检查产物对不对，不对就回 planning 重来 |
| [backend/runtime/nodes/finalize.py](../../backend/runtime/nodes/finalize.py) | **整理节点**：把零散结果汇总成最终回答 |
| [backend/runtime/routes/next_step.py](../../backend/runtime/routes/next_step.py) | planning 之后的条件路由（去 tools / await_user / verify / finalize 哪个） |
| [backend/runtime/routes/post_tools.py](../../backend/runtime/routes/post_tools.py) | tools 之后的条件路由 |
| [backend/runtime/context_registry.py](../../backend/runtime/context_registry.py) | **新增**。给 tool 提供"当前 session 上下文"的注册表（这样 tool 函数能拿到 session_id） |
| [backend/runtime/session_sync.py](../../backend/runtime/session_sync.py) | RuntimeState ↔ SessionState 双向同步 |

**前端只看 4 个 phase**（planning/tools/verify/finalize），但 graph 实际有 **5 个节点**。第 5 个 await_user 在前端层面被映射为 `status="awaiting_user"` 而不是独立 phase——这是个聪明的简化。

**LangGraph 的厉害之处**：
- `MemorySaver` checkpointer（runtime.py:38）让任务可以"暂停-继续"
- 用 `interrupt()` 抛 `RuntimePaused` 异常，外层 catch 后等用户 resume，再用 `Command(resume=...)` 把数据塞回去继续跑
- 这一套是 LangGraph 0.2+ 的原生玩法，贤接得很稳

### 3.4 Worker 层（F05 的核心）

| 文件 | 干啥的 |
|---|---|
| [backend/workers/selection.py](../../backend/workers/selection.py) | **路由规则**：按关键词选 worker |
| [backend/workers/registry.py](../../backend/workers/registry.py) | worker 注册表，从 config 加载可用 worker |
| [backend/workers/codex_worker.py](../../backend/workers/codex_worker.py) | Codex CLI 包装层 |
| [backend/workers/opencode_worker.py](../../backend/workers/opencode_worker.py) | OpenCode CLI 包装层 |
| [backend/workers/claude_worker.py](../../backend/workers/claude_worker.py) | Claude CLI 包装（备用） |
| [backend/runners/python_runner.py](../../backend/runners/python_runner.py) | **Python 沙盒**。这次重点改的：内置 sklearn 线性回归 demo（146-184 行 `_default_demo_code_for_task`）；输出截断（217-226 行）；artifact 自动 diff 工作区 |
| [backend/runners/codex_runner.py](../../backend/runners/codex_runner.py) | spawn codex CLI 子进程 |
| [backend/runners/opencode_runner.py](../../backend/runners/opencode_runner.py) | spawn opencode CLI 子进程 |
| [backend/tools/delegate.py](../../backend/tools/delegate.py) | **委派 + fallback 总入口**。所有 worker 都挂时返回 `worker:"fallback"` 兜底（239-249 行） |

**Worker 选型规则（背下来）**：
```
任务文本含 review/analyze/inspect/explain/diagnose  → codex
任务文本含 implement/write/create/fix/refactor      → opencode
含 python/sklearn 等代码意图                        → python_runner
都不命中                                            → opencode → codex → fallback
```

**Fallback 兜底逻辑** = "三个 worker 都挂了 → 返回 'worker:"fallback"' 假装跑过了 → 任务不崩，前端显示完成 + 提示" 这是 F05 验收点 2 的核心。

### 3.5 工作区层（产物落在哪）

| 文件 | 干啥的 |
|---|---|
| [backend/workspace_meta/store.py](../../backend/workspace_meta/store.py) | **新增模块** 246 行，工作区元数据持久化（任务有哪些产物，哪个工作区是哪个任务的） |
| [backend/workspace_meta/service.py](../../backend/workspace_meta/service.py) | 服务层 114 行，给前端 / 编排查工作区信息 |

**工作区约定**：
- 没显式传 workspace → 落到 `scratch/tasks/<task_id>/`
- python_runner 跑完会 `diff_workspace()`，自动把新增 / 修改的文件登记到 `session.artifacts`
- 前端 artifacts 字段就是这么来的

---

## 4 · 前端文件分组讲解

后端 A 顺手做了**前端的 4 个核心文件**，所以你看仓库里这些不是前端 B 写的。

### 4.1 状态管理

| 文件 | 干啥的 |
|---|---|
| [TutorGridFront/src/stores/orchestratorStore.ts](../../TutorGridFront/src/stores/orchestratorStore.ts) | **底层 ws store**。负责连接 / 重连 / 发请求 / 订阅事件。不区分协议版本 |
| [TutorGridFront/src/stores/orchestratorTaskStore.ts](../../TutorGridFront/src/stores/orchestratorTaskStore.ts) | **任务级 store**（V5 新增）。订阅 task.\* 事件，把它们按 task_id 攒成 `OrchestratorTaskItem` 对象，UI 直接绑这个 |

`orchestratorTaskStore` 的核心 API：
```ts
createTask({ docId, instruction, workspace?, runner? })
   → 发起任务，自动订阅事件，返回 {task_id, session_id}
resumeTask(taskId, content)
   → 恢复 awaiting_user 的任务
interruptTask(taskId)
   → 中断
activeTaskForDoc(docId)  // getter
   → 拿当前文档的活动任务（磁贴绑这个）
```

订阅逻辑在 `_ensureSessionSubscription()` (107 行)，监听 3 个事件：
- `task.step` → 更新当前阶段、进度、active_worker
- `task.awaiting_user` → 标记 awaitingUser=true，存 prompt
- `task.result` → 存最终 content、artifacts、worker_runs，把所有 step 标 done

### 4.2 UI 组件

| 文件 | 干啥的 |
|---|---|
| [TutorGridFront/src/views/document/components/tiles/TaskTile.vue](../../TutorGridFront/src/views/document/components/tiles/TaskTile.vue) | **磁贴**。三种尺寸（1x1/1x2/2x2）适配。已有：新建任务弹窗 / 4 步进度条 / 中断 / 继续 / 跳详情 |
| [TutorGridFront/src/views/pages/TaskDetailsPage.vue](../../TutorGridFront/src/views/pages/TaskDetailsPage.vue) | **详情页**。路由 `/tasks/:id`。展示完整步骤列表 / artifacts / worker_runs |

**磁贴的 size prop**：
- `1x1` (compactMode)：极简，只一个标签 + 状态
- `1x2`：中等，加进度条
- `2x2` (largeMode)：完整，能直接输入指令启动（不用弹窗）

### 4.3 Electron 启动

| 文件 | 干啥的 |
|---|---|
| [TutorGridFront/electron/main.ts](../../TutorGridFront/electron/main.ts) | Electron 主进程。启动时 **自动 spawn 两个 Python 进程**：HTTP 后端 (8000) + Orchestrator (3210)。智能找 Python 解释器（先看 PYTHON_EXECUTABLE → VIRTUAL_ENV → CONDA_PREFIX → 仓库 .venv → 系统 python） |

**注意一个 hardcode**：`DEFAULT_WORKSPACE_ROOT = "D:\\SoftInnovationCompetition\\TestFolder"` (electron/main.ts:74)。这是工作区默认根目录，**写死的 D 盘**，Mac/Linux 上跑要改。

---

## 5 · 这几天他到底改了什么（按 commit 串）

```
36f791f  feat(F04): 重写编排协议并更新配置页与CI
   ↓ 把 session.* 协议投影出 task.* 一层
   ↓ protocol.py 加字段；app.py 加 task.create/resume/interrupt 三个 dispatch

1d78418  feat(F04): 接入编排任务前端与自动启动后端
   ↓ 顺手把前端三件套（store / TaskTile / TaskDetailsPage）写了
   ↓ Electron main.ts 加自动 spawn

0074348  feat(F04): 推进编排流式接入并补全F05结果回传
   ↓ runtime.py 接入 LangGraph stream v2 流式
   ↓ tools 节点开始往外推 active_worker / step 事件
   ↓ task.result 携带完整 worker_runs

58f9624  feat(F05): 补全文派降级并收口F04中断恢复
   ↓ delegate.py 加 fallback 兜底
   ↓ await_user 节点对接 RuntimePaused 异常
   ↓ resume 链路打通：waiter Future → 节点 Command(resume) 

fc9141a  feat(F04,F05): 完善编排任务流程和出错处理
   ↓ 收尾：python_runner 内置 sklearn 兜底 demo
   ↓ task workspace 落到 scratch/tasks/<id>/
   ↓ workspace_meta 模块新增（任务产物登记）
   ↓ task.result 错误码、failed 路径补全
```

总结：**协议层重写 → 前端配套 → 流式接入 → fallback 兜底 → 收尾打磨**，节奏其实挺好。

---

## 6 · 重构亮点 + 留下的坑

### 亮点（演示时可以吹）
1. **新老协议双轨并存**：旧 `session.*` 协议用作 GUI 调试 / 回归测试；新 `task.*` 协议给前端用。新前端不破坏老测试。
2. **LangGraph 原生 interrupt/resume**：用 `RuntimePaused` 异常 + `Command(resume=...)` 实现"问用户"这种交互式中断，是 LangGraph 0.2+ 的标准玩法，没自己造轮子。
3. **Fallback 不崩**：三个 worker CLI 任意挂掉，整个任务还能完成（虽然只是纯 LLM 推理）。演示机配置不全也能演。
4. **工作区收口**：所有任务产物落到 `scratch/tasks/<task_id>/`，不污染主仓库；artifact 自动 diff，不用手动登记。

### 坑（自己心里有数）
1. **app.py 1300+ 行** — 太长，dispatch 没拆。改字段时要全文搜，别想着重构（答辩前别动）。
2. **session 不持久化** — 后端进程重启 → 任务全丢。中等优先级，演示时不要重启就行。
3. **协议文档与实现对不上**（之前你已经发现）：
   - 验收指南示例用 `type:"response"` 但实际是 `type:"event"`
   - resume 文档示例用嵌套 `input:{kind,content}` 但实际是平坦 `content/kind`
   - 这是文档要勘误，不是代码 bug
4. **`DEFAULT_WORKSPACE_ROOT` 在 Electron 里硬编 D 盘** — Mac 答辩机要改。
5. **awaiting_user 触发不稳** — 依赖 LLM 是否调 `await_user` 工具，prompt 写得不明确就不触发。这是 LLM 行为问题，不是后端 bug。

---

## 7 · 跟旧版（V4 session 协议）的区别

| 维度 | 旧 V4（`orchestrator.session.*`） | 新 V5（`orchestrator.task.*`） |
|---|---|---|
| 抽象层级 | 会话级（一个 ws 会话 = 一个 session） | 任务级（一个文档可有多任务并发） |
| 主入口 | `session.start` | `task.create` |
| 进度推送 | `session.progress`（自由文本） | `task.step`（结构化 phase/status/step_index） |
| 用户交互 | `session.await_user` | `task.awaiting_user` + `task.resume` |
| 结果 | `session.completed`（result 字符串） | `task.result`（result_type / artifacts / worker_runs 三件套） |
| 文档绑定 | 没有 | `doc_id` 字段，原生支持文档内任务 |

**为什么要有 V5**：F12 要求"文档里 `/task` 注册任务"，这就要求**一个文档能有多个任务、任务跟文档绑定**。旧 V4 是"一个会话调一次"的 GUI 调试协议，扛不住这个。

---

## 8 · 你最关心的 3 个问题（FAQ）

**Q1：他到底是真完成了 F04/F05 还是糊弄？**
> 实现是**真做了**，文档相对于代码**有 3 处过时示例**。代码层面的 4 个核心承诺（4 步流式 / 委派路由 / fallback 不崩 / sklearn 出图）都能在源码里找到对应。验证方法见 [F04-F05-验收指南.md](./F04-F05-验收指南.md)。

**Q2：F04 / F05 跟 F12 的边界？**
> F04/F05 = **后端**编排引擎本身（贤的活，已完成）
> F12 = **前端**`/task` slash 命令在文档里触发任务的入口（你的活，没做）
> 但磁贴 UI 已就绪，**不接 F12 也能从磁贴起任务**（磁贴有"新建任务"按钮）。F12 是锦上添花，不是 F04/F05 的依赖。

**Q3：演示 30 秒能演成功的最短路径？**
> 启 Electron → 进任意 hyperdoc → 在右侧"编排任务"磁贴点"新建任务" → 输入"用 sklearn 跑线性回归，把图保存成 plot.png" → 等 15-30 秒 → 磁贴 4 步走绿 → 点"查看详情"看 PNG 产物。**这就是答辩保底链路。**

---

*最后更新：2026-05-04 · 维护：前端 A · 波 + 协助 AI*
*基于代码版本：fc9141a (F04/F05 收尾完成)*
