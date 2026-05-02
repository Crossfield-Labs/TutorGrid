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

## 接下来应该做什么

建议顺序：

1. 在 `backend/server/protocol.py` 增加：
   - `orchestrator.task.create`
   - `orchestrator.task.resume`
   - `orchestrator.task.interrupt`

2. 在 `backend/server/app.py` 增加任务级事件投影：
   - `orchestrator.task.step`
   - `orchestrator.task.result`
   - `orchestrator.task.awaiting_user`

3. 在 `backend/runtime/` 收口中断恢复：
   - 用 `interrupt()` 表达等待用户输入
   - 用 `resume` 恢复执行

4. 最后再让前端文档入口接 `orchestrator.task.create`

## 修改时注意

- 新的前端编排入口不要继续扩展旧 `orchestrator.session.*`
- 运行时内部状态变化，不要直接暴露给前端
- 如果任务级 frame 有变化，先更新 `../../docs/orchestrator-v5-protocol.md`
