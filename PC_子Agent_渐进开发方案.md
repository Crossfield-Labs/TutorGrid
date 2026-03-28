# MetaAgent PC 子 Agent 渐进开发方案

## 1. 文档目标

这份文档用于指导 `pc_orchestrator/` 的实际开发，目标不是写一个“远程执行命令的小脚本”，而是设计一套可持续扩展、可支撑复杂任务、可与 Android 主编排树深度协作的 **PC 子调度 Agent**。

本文档服务以下目标：

- 明确 Android 主调度与 PC 子调度之间的职责边界
- 明确 PC 端为什么要做成 `session-based sub-agent`，而不是一次性 CLI 调用
- 明确第一版最小可运行闭环的开发范围
- 明确后续如何平滑扩展到复杂任务、多执行器路由、异步双线程
- 给每一步开发配套验收测试，避免“看起来设计很好，但跑不起来”

---

## 2. 核心产品目标

MetaAgent 的核心不是“再做一个能跑命令的控制台”，而是：

> **让 AI 代替用户去调度其他 AI / 工具 / 执行器，并把思考过程、执行过程、关键决策点实时同步给用户。**

围绕这个目标，PC 端的正确定位不是：

- Android 远程发一条命令给 PC
- PC 跑完后回一段结果

而是：

- Android 作为 **主调度器**
- PC 作为 **子调度 Agent**
- PC Agent 再决定内部调用：
  - Claude Code / Claude CLI
  - Codex CLI / OpenCode
  - Shell / Python / Git / 测试运行器
  - 后续 Browser / Local Runner / Report Generator

也就是说：

```text
用户
 -> Android 主 Agent（主编排树）
 -> PC 子 Agent（执行子树 / 子会话）
 -> 具体 runner（Claude / Codex / Shell / Python / ...）
```

---

## 3. 设计原则

### 3.1 主调度权在 Android，不在 PC

Android 端必须继续保留：

- 任务理解
- 主编排树生成
- 主树审批
- 进度可视化
- 前台聊天与陪伴
- 用户插话、改方向、确认继续

PC 不应替代 Android 成为产品主入口。

### 3.2 PC 必须是子 Agent，不是单次工具调用

PC 节点必须支持：

- 持续执行
- 流式进度回传
- 中途等待用户输入
- 继续执行
- 内部子步骤
- 多 runner 路由

所以 PC 节点应设计成 **session**，而不是简单的 RPC。

### 3.3 Runner 是插件，PC 子 Agent 是中枢

PC 不直接等于 Claude。

PC 子 Agent 下应该能挂：

- `claude_cli`
- `codex_cli`
- `opencode_cli`
- `shell`
- `local_runner`

后续再加：

- `browser`
- `dify`
- `report_builder`

### 3.4 先做轻量版，不直接上重型 LangGraph

产品书里 PC 端推荐 `Python + FastAPI + LangGraph`，方向正确。

但第一版开发不建议一开始就引入完整 LangGraph 图执行。
第一版先做：

- WebSocket session server
- session manager
- runner router
- 基础状态机

第二阶段再考虑 LangGraph 化。

### 3.5 UI 壳子和执行核心分离

建议固定技术栈：

- PC orchestrator：**Python**
- PC 桌面壳子：**WinUI 3**

不要用 Electron 做主壳。
不要让 WinUI 3 承载执行核心。

---

## 4. 系统总架构

```text
Android App
  ├── Chat / Agent 模式
  ├── 主编排树（主任务）
  ├── 用户审批 / 插话 / 确认
  └── WebSocket Client
            │
            ▼
PC Orchestrator (Python)
  ├── WS Session Server
  ├── Session Manager
  ├── Runner Router
  ├── PC Sub-Agent Runtime
  ├── Event Bus
  └── State Store
            │
            ▼
Runners
  ├── Claude CLI
  ├── Codex CLI
  ├── OpenCode CLI
  ├── Shell / PowerShell
  ├── Python Runner
  └── Local Task Runner
```

---

## 5. Android 与 PC 的职责边界

## 5.1 Android 负责什么

- 接收用户目标
- 判断是否进入 Agent 模式
- 生成主编排树
- 决定什么时候触发 `PC` 节点
- 展示主树节点状态与进度
- 在 PC 执行期间继续和用户聊天
- 将用户新的指令、确认、修改同步给 PC

## 5.2 PC 负责什么

- 接收一个 `PC` 主节点的执行请求
- 在本地生成内部执行计划或子步骤
- 选择最合适的 runner
- 流式执行与回传
- 关键节点停下来，等待用户进一步指令
- 继续执行并产出结果

## 5.3 Runner 负责什么

- 真正执行命令、代码、测试、训练、报告生成
- 不直接和 Android 通信
- 不直接做产品逻辑决策

---

## 6. PC 节点模型设计

Android 主编排树中新增一个清晰的 `PC` 节点语义：

```json
{
  "id": "pc_train_01",
  "title": "在电脑端运行 CNN 训练并持续分析结果",
  "goal": "在当前项目中检查环境、运行训练、在需要时请求用户确认调参，并输出训练曲线与实验报告草稿。",
  "adapter": "PC",
  "toolName": "pc.execute",
  "toolParams": {
    "runner": "claude_cli",
    "workspace": "D:/workspace/cnn-lab",
    "task": "检查当前项目，运行 CNN 实验，并在需要调参时先问用户"
  },
  "dependsOn": ["node_discuss_plan"],
  "requiresApproval": true
}
```

关键点：

- `adapter = PC`
- `toolName = pc.execute`
- `runner` 作为二级路由参数
- 主树只把它看作一个远端执行块

---

## 7. WebSocket 通信设计

PC 端不应设计为普通请求响应，而应设计为 **session 化事件流**。

## 7.1 Android -> PC

- `pc.session.start`
  - 开始一个 PC 节点会话
- `pc.session.input`
  - 对当前 session 补充输入、确认、改方向
- `pc.session.pause`
- `pc.session.resume`
- `pc.session.cancel`
- `dialogue.message`
  - Android 主聊天给 PC 的额外问答或上下文

## 7.2 PC -> Android

- `pc.session.started`
- `pc.session.progress`
- `pc.session.await_user`
- `pc.session.subnode.started`
- `pc.session.subnode.completed`
- `pc.session.completed`
- `pc.session.failed`
- `dialogue.reply`

## 7.3 设计理由

如果只设计成：

- `task.execute_node`
- `node.completed`

那么系统会失去：

- 中途插话
- 中途确认
- 流式解释
- 内部子步骤投影
- 长任务恢复

而这些恰恰是产品书强调的“共做”和“异步双线程”的核心。

---

## 8. PC Session 内部状态机

PC 子 Agent 需要一个最小状态机：

```text
IDLE
 -> STARTING
 -> RUNNING
 -> AWAIT_USER
 -> RUNNING
 -> COMPLETED / FAILED / CANCELLED
```

建议定义：

- `session_id`
- `task_id`
- `node_id`
- `status`
- `runner`
- `workspace`
- `context`
- `history`
- `artifacts`
- `last_progress_message`

---

## 9. Runner Router 设计

PC 端不要把所有任务都塞给 Claude。

建议设计成：

```text
RunnerRouter
  -> choose runner based on node/tool/task context
```

第一阶段支持：

- `claude_cli`
- `shell`
- `local_runner`

第二阶段加入：

- `codex_cli`
- `opencode_cli`

第三阶段加入：

- `browser`
- `report_builder`

## 9.1 第一阶段路由规则

- 环境检查、目录检查、依赖查询
  - `shell`
- 代码补全、修复、解释
  - `claude_cli`
- 跑测试、跑训练、生成日志
  - `local_runner`

## 9.2 后续增强路由

- 如果代码任务长、需要第二意见
  - `codex_cli`
- 如果 Claude 卡住或不稳定
  - 可以自动切换 `opencode_cli`

这正是你想要的：

> 一个不行，就换另一个去调度它干活

---

## 10. 为什么不是直接用 NanoClaw

`nanoclaw` 值得参考，但不建议原样改造为 PC orchestrator。

## 10.1 可借鉴的部分

- session 持续 query 的思路
- IPC 输入继续执行
- 队列与并发控制
- remote control 的思路

## 10.2 不建议直接复用的部分

- channels
- groups
- 频道消息轮询
- OneCLI 体系
- 个人 Claude 助手产品层

## 10.3 结论

**借思路，重写轻量版。**

这是最稳的方案。

---

## 11. 三步渐进开发计划

# Step 1：打穿最小 PC 节点闭环

## 目标

让 Android 主编排树第一次真正触发一个 `PC` 节点，并看到 PC 真实执行。

## 范围

- WebSocket server
- `pc.session.start`
- `pc.session.progress`
- `pc.session.completed`
- `pc.session.failed`
- runner 仅支持：
  - `shell`
  - `claude_cli`

## 实现内容

### PC 端

- `server/`
  - WebSocket 接入
- `session_manager/`
  - 创建和管理 session
- `runner_router/`
  - 根据 `runner` 字段路由
- `runners/shell_runner.py`
- `runners/claude_runner.py`

### Android 端

- `PlanNodeAdapter.PC`
- `executePcNode()`
- `MetaAgentWSClient`
- 将 PC progress 映射到 `TaskSession`

## 这一阶段不做

- 中途继续输入
- 子步骤可视化
- Codex / OpenCode
- 状态持久化
- WinUI 3 壳子

## 验收测试

### 测试 1：最小 Shell 任务

用户输入：

```text
帮我在电脑上检查当前项目目录结构并总结
```

预期：

- 生成主树中出现 `PC` 节点
- PC 真执行目录检查
- Android 实时看到 progress
- 完成后得到总结

### 测试 2：最小 Claude 任务

用户输入：

```text
帮我在电脑上创建一个 hello.py 并运行
```

预期：

- PC 节点调用 `claude_cli`
- Android 看到流式输出
- 最终完成并返回结果

### 成功标准

- 安卓能发起 PC session
- PC 能执行
- Android 能持续显示进度
- 节点状态正常完成或失败

---

# Step 2：让 PC 节点成为“可持续子 Agent”

## 目标

让一个 `PC` 节点不再是一次性黑盒，而是可以：

- 中途等待用户
- 继续执行
- 持续保有上下文

## 范围

- `pc.session.input`
- `pc.session.await_user`
- session 内历史上下文
- session 恢复继续
- 内部子步骤事件投影

## 实现内容

### PC 端

- session history 存储
- `await_user` 状态
- 接收新输入继续执行
- `subnode.started/completed` 事件

### Android 端

- `PC` 节点卡片支持“等待确认/补充输入/继续”
- Chat 输入可继续喂给当前 PC session

## 这一阶段不做

- 多 runner 自动切换
- 完整 LangGraph 图执行
- WinUI 3 壳子

## 验收测试

### 测试 1：测试跑完后继续

用户输入：

```text
帮我把课程项目代码跑一遍测试，整理日志
```

中途 PC 汇报：

```text
14/16 通过，7 和 12 失败。要先整理通过项还是深挖失败项？
```

用户回复：

```text
先把通过的整理成报告
```

预期：

- PC session 不重建
- Android 继续同一个 PC 节点
- 后台继续执行
- 最终返回通过项报告

### 测试 2：训练中调参

用户输入：

```text
帮我继续完成 CNN 实验，但关键决策先问我
```

PC 中途汇报：

```text
accuracy 波动，建议把 lr 调到 0.001，要试吗？
```

用户回复：

```text
试试
```

预期：

- Android 前台能收到询问
- 用户回复后 PC session 继续
- 训练完成并产出曲线图/总结

### 成功标准

- 一个 PC 节点内支持多轮输入
- Android 与 PC 真正形成共做
- 异步双线程开始成形

---

# Step 3：升级成“多 runner 可切换的 PC 子调度 Agent”

## 目标

让 PC 不只是执行器，而是开始具备真正的子调度能力：

- 按任务类型选择不同 runner
- 某个 runner 不适合时可以切换
- 内部子步骤更清晰
- 更适合复杂任务

## 范围

- `codex_cli`
- `opencode_cli`
- `runner fallback / reroute`
- 更清晰的子步骤事件
- 状态持久化
- 可选 WinUI 3 壳子接入

## 实现内容

### PC 端

- `codex_runner.py`
- `opencode_runner.py`
- `runner selection strategy`
- session state store（SQLite/JSON）
- failure-based reroute

### Android 端

- `PC` 节点可展开查看内部子步骤
- 连接状态可见
- 更好的日志投影

### WinUI 3（可选）

- 本地任务仪表盘
- session 状态
- 日志面板
- 审批按钮

## 验收测试

### 测试 1：代码补全 + 失败切换

用户输入：

```text
帮我补完当前 CNN 实验代码并跑一遍
```

预期：

- PC 子 Agent 先选 `claude_cli`
- 若执行失败或判断不合适，可切到 `codex_cli`
- Android 持续看到进度和切换信息

### 测试 2：复杂任务组合

用户输入：

```text
帮我跑测试、整理日志、补通过项报告，失败项先记录下来
```

预期：

- 一个 `PC` 节点内部出现多个子步骤
- Android 展示的是主树 + PC 子步骤投影
- 用户仍可前台插话

### 成功标准

- PC 开始具备真正“子调度”能力
- 不同 runner 可被统一调度
- Android 仍保有主树与用户控制权

---

## 12. 推荐目录结构

建议最终目录：

```text
pc_orchestrator/
  README.md
  PC_子Agent_渐进开发方案.md
  requirements.txt
  server/
    app.py
    websocket_server.py
    protocol.py
  sessions/
    session_manager.py
    session_state.py
    state_store.py
  router/
    runner_router.py
  runners/
    base.py
    shell_runner.py
    claude_runner.py
    codex_runner.py
    opencode_runner.py
    local_runner.py
  events/
    event_bus.py
    event_models.py
  utils/
    logging.py
    subprocess_stream.py
```

---

## 13. 性能与扩展性要求

为了适配后续复杂任务，第一版就应坚持这些约束：

- **session 内部无阻塞主线程**
  - 所有 runner 输出流必须异步读取
- **事件模型稳定**
  - 后续新增 runner 不应推翻协议
- **Android 不感知 runner 细节**
  - Android 只理解 `PC session`
- **PC 保持 session 级上下文**
  - 避免每次从零开始
- **状态可恢复**
  - 后续断线重连、后台恢复要有空间

---

## 14. 最终推荐结论

PC 的最佳定位不是：

- Android 远程调一个 CLI

而是：

- Android 主 Agent 调起一个 **PC 子 Agent session**
- PC 子 Agent 在本地再去调度 Claude / Codex / Shell / Runner
- 通过 WebSocket 事件流持续把过程投影回 Android 主编排树

这样才能真正实现你设想的：

> **我们的 AI 不是自己埋头干活，而是替你去调度会干活的执行器，并且让你始终知道发生了什么。**

