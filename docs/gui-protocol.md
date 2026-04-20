# GUI 协议与数据需求

这份文档定义桌面 GUI 第一版需要后端补的协议和字段，目标是：
- 复用现有 WebSocket 协议
- 不让前端直接依赖 runtime 内部对象
- 尽量减少后续前后端返工

## 前端技术方向

当前约定：
- GUI 使用 TypeScript
- 桌面壳使用 Electron
- 优先 WebSocket
- 历史查询可以补轻量拉取接口

前端不应该直接消费：
- `session.context`
- runtime graph 内部 state
- worker 内部私有 metadata

前端应该消费：
- 稳定的 `snapshot`
- 稳定的 session 列表数据
- 稳定的事件流
- trace / history 查询结果

## 第一版 GUI 页面结构

### 1. 会话列表

需要字段：
- `sessionId`
- `task`
- `runner`
- `status`
- `phase`
- `latestSummary`
- `activeWorker`
- `updatedAt`

### 2. 主时间线

需要展示：
- progress
- phase 变化
- substeps
- tool 摘要
- worker 状态变化
- summary
- errors

### 3. 状态侧栏

需要字段：
- `status`
- `phase`
- `stopReason`
- `activeWorker`
- `activeSessionMode`
- `activeWorkerProfile`
- `activeWorkerCanInterrupt`
- `awaitingInput`
- `pendingUserPrompt`
- `latestArtifactSummary`
- `permissionSummary`
- `sessionInfoSummary`
- `mcpStatusSummary`

### 4. 输入区

第一版至少支持：
- reply
- redirect
- instruction
- explain
- interrupt

## 现有 WebSocket 事件可直接复用的部分

当前已有：
- `orchestrator.session.progress`
- `orchestrator.session.phase`
- `orchestrator.session.worker`
- `orchestrator.session.summary`
- `orchestrator.session.artifact_summary`
- `orchestrator.session.permission`
- `orchestrator.session.mcp_status`
- `orchestrator.session.worker_runtime`
- `orchestrator.session.snapshot`

这部分应该继续保留。

## 需要新增的历史查询能力

GUI 不能只靠实时事件，还需要历史拉取。

建议新增这些方法：

### 1. `orchestrator.session.list`

用途：
- 加载会话列表

请求：
```json
{
  "type": "req",
  "id": "req-list-1",
  "method": "orchestrator.session.list",
  "params": {
    "limit": 50,
    "cursor": ""
  }
}
```

响应 payload 建议：
- `items`
- `nextCursor`

每个 item 至少有：
- `sessionId`
- `task`
- `runner`
- `status`
- `phase`
- `latestSummary`
- `activeWorker`
- `updatedAt`

### 2. `orchestrator.session.history`

用途：
- 拉指定 session 的时间线历史

请求：
```json
{
  "type": "req",
  "id": "req-history-1",
  "method": "orchestrator.session.history",
  "sessionId": "session-1",
  "params": {
    "limit": 200,
    "cursor": ""
  }
}
```

响应 payload 建议：
- `items`
- `nextCursor`

每个 item 建议字段：
- `seq`
- `kind`
- `event`
- `title`
- `status`
- `detail`
- `createdAt`

当前实现：
- 已支持 `items`
- 每个 item 已包含 `seq / kind / event / title / status / detail / createdAt`

### 3. `orchestrator.session.trace`

用途：
- 拉原始 trace / 调试事件

### 4. `orchestrator.session.errors`

用途：
- 拉结构化错误

### 5. `orchestrator.session.messages`

用途：
- 拉 planner message history

## snapshot 字段还需要补什么

当前 `backend/sessions/state.py` 已有很多字段，但为了 GUI 更稳定，建议后续补到 `build_snapshot()`：
- `stopReason`
- `updatedAt`
- `createdAt`
- `runner`
- `task`
- `goal`
- `error`

当前实现：
- 上述字段已经并入 snapshot

这样 GUI 首屏不需要额外拼太多字段。

## GUI 第一版建议的事件模型

前端内部可以统一成：

- `session-meta`
- `phase`
- `progress`
- `substep`
- `summary`
- `worker`
- `snapshot`
- `error`
- `artifact`

后端不一定真的改成这些名字，但最终要能映射到这个统一前端模型。

## 与 LangGraph / LangChain 的关系

### LangGraph

对 GUI 来说，LangGraph 的作用是提供稳定状态流：
- phase 变化
- 暂停与恢复
- stop reason
- 可回放的执行步骤

GUI 看到的“任务正在怎样推进”，本质上来自 LangGraph state 的投影。

### LangChain

对 GUI 来说，LangChain 的作用主要体现在展示内容：
- planner summary
- tool 摘要
- 压缩后的摘要
- 错误解释

GUI 不需要知道 LangChain 内部对象，只需要消费它产出的稳定字段。

## 第一阶段验收标准

GUI 第一版上线前，后端至少要做到：
1. 会话列表可拉取
2. 指定 session 最新 snapshot 可拉取
3. session 时间线历史可拉取
4. reply / redirect / explain / interrupt 通过统一协议可调用
5. 错误详情可拉取

