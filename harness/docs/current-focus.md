# 当前任务与交接点

这份文档只记录当前这轮最重要的交接信息。

## 当前主线

当前主线已经完成任务书 `F04 / F05` 的后端 A 范围：
- 已将现有 LangGraph 编排图适配到 V5 的文档内注册任务模式
- 对外主协议已从旧的 `orchestrator.session.*`，切到 `orchestrator.task.*`
- Worker / CLI / Python Runner 委派链路已交付
- 当前文档只处理编排与委派部分，不包含 RAG

## 当前判断

F04 / F05 现在的判断是：**功能已完成，进入稳定化与后续增强阶段**。

F04 的做法不是重写后端，而是做定向适配：

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
- 新增 `../../docs/BackEndA/orchestrator-v5-protocol.md`
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

1. 继续做稳定化：
   - 清理旧进程混跑导致的联调误判
   - 保持 `task.result` / `worker_runs` / `artifacts` 字段稳定
   - 继续观察真实模型下的多轮规划体验

2. 继续增强 LangGraph stream 的结构化事件：
   - progress
   - substep
   - final result

3. 前后端继续推进非 F04 / F05 范围：
   - 前端 F12 `/task` 文档内注册入口
   - 其他 GUI 能力
   - 非编排模块的持久化与产品化

## 修改时注意

- 新的前端编排入口不要继续扩展旧 `orchestrator.session.*`
- 运行时内部状态变化，不要直接暴露给前端
- 如果任务级 frame 有变化，先更新 `../../docs/BackEndA/orchestrator-v5-protocol.md`
