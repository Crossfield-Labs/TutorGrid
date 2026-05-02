# 当前任务与交接点

这份文档只记录当前这轮最重要的交接信息。

## 当前主线

当前主线已经切到任务书 `F04`：
- 将现有 LangGraph 编排图适配到 V5 的文档内注册任务模式
- 对外主协议从旧的 `orchestrator.session.*`，切到 `orchestrator.task.*`
- 只处理编排部分，不包含 RAG

## 当前判断

F04 的正确做法不是重写后端，而是做定向适配：

1. 保留现有 runtime 骨架
   - `planning -> tools -> verify -> finalize`

2. 保留现有 session 状态层
   - 等待输入
   - 产物
   - 快照

3. 在 server 层补任务级协议投影
   - `orchestrator.task.create`
   - `orchestrator.task.step`
   - `orchestrator.task.result`
   - `orchestrator.task.awaiting_user`
   - `orchestrator.task.resume`
   - `orchestrator.task.interrupt`

## 本轮先完成了什么

### 1. 文档口径收口
- 新增 `../../docs/orchestrator-v5-protocol.md`
- 旧 `../../docs/gui-protocol.md` 不再维护旧编排会话协议，改成兼容跳转入口
- `server.md` 改为只描述 F04 的任务级编排协议面

### 2. 范围切分明确
- 本轮只改编排协议文档
- 不改任务书
- 不改 RAG / 知识库文档

### 3. F04 / F05 已推进到的代码面
- `backend/server/app.py` 已支持：
  - `orchestrator.task.create`
  - `orchestrator.task.resume`
  - `orchestrator.task.interrupt`
  - `orchestrator.task.step`
  - `orchestrator.task.awaiting_user`
  - `orchestrator.task.result`
- `backend/runtime/` 已开始改成优先消费 LangGraph stream：
  - 优先走 `astream(stream_mode=["custom", "values"])`
  - `session_sync.py` 会优先用 `get_stream_writer()` 写 `custom` 进度事件
- `backend/runtime/` 已开始把等待输入收口到 LangGraph 原生暂停：
  - `tools_node` 会把 `await_user` 工具改写成 graph 内等待输入状态
  - `await_user_node` 用 `interrupt()` 暂停
  - `task.resume` 可通过 `Command(resume=...)` 恢复
- `backend/runners/python_runner.py` 现在会把：
  - `stdout/stderr`
  - workspace artifact diff
  - `worker_runs`
  一并回写到 session，再投影到 `task.result`

## 接下来应该做什么

建议顺序：

1. 在 `backend/runtime/` 继续收口中断恢复：
   - 把当前“兼容旧 waiter + graph resume”的双路径再继续压成单一路径
   - 给原生 `interrupt/resume` 补更完整的集成测试

2. 继续增强 LangGraph stream 的结构化事件：
   - progress
   - substep
   - final result

3. 做 F05 的真实 worker / runner 验收：
   - python runner 编排闭环
   - delegate fallback 闭环
   - `task.result` 对前端字段稳定性校验

## 修改时注意

- 新的前端编排入口不要继续扩展旧 `orchestrator.session.*`
- 运行时内部状态变化，不要直接暴露给前端
- 如果任务级 frame 有变化，先更新 `../../docs/orchestrator-v5-protocol.md`
