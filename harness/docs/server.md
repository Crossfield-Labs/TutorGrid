# Server 模块

主要代码：
- `backend/server/app.py`
- `backend/server/protocol.py`

这份文档只描述 F04 对应的编排协议面。

不在本文档范围内：
- Chat SSE
- RAG / 知识库 REST
- 学习画像 REST

## 当前职责

Server 在 F04 阶段的职责是：
- 暴露 `WS /ws/orchestrator`
- 接收任务级编排请求
- 把 runtime / session 的内部状态投影成稳定的 V5 编排事件
- 负责中断、恢复、结果回传这些对前端可见的编排行为

## 当前主协议

V5 编排主协议见：
- `../../docs/orchestrator-v5-protocol.md`

当前对前端应优先维护的请求：
- `orchestrator.task.create`
- `orchestrator.task.resume`
- `orchestrator.task.interrupt`

当前对前端应优先维护的事件：
- `orchestrator.task.step`
- `orchestrator.task.result`
- `orchestrator.task.awaiting_user`

## 内部适配关系

F04 不是重写后端，而是在现有后端上做协议适配。

当前建议分层：

1. `runtime`
   - 保留 `planning -> tools -> verify -> finalize`

2. `sessions`
   - 继续维护运行状态、等待输入、产物、快照

3. `server`
   - 对外把旧的 session 级状态映射成 task 级协议

映射方向：
- 内部启动链路 -> `orchestrator.task.create`
- `phase / summary / worker / progress` -> `orchestrator.task.step`
- 完成 / 失败 / 产物 -> `orchestrator.task.result`
- 等待用户输入 -> `orchestrator.task.awaiting_user`

当前已落地的关键行为：
- `task.resume` 先兼容旧 waiter 恢复路径
- 对 graph 原生 `interrupt()` 暂停的任务，`task.resume` 会写入 `_resume_payload` 并重新拉起 runtime
- `task.result` 会带 `worker_runs` 与结构化 `artifacts`

## 旧协议的定位

仓库里现有的 `orchestrator.session.*` 仍然存在，但在 F04 阶段的定位是：
- 历史调试契约
- 内部适配基础
- 回归测试辅助通道

不再作为 V5 前端编排接口的主要扩展面。

## 修改时注意

- 请求解析放在 `protocol.py`
- 连接、订阅、广播行为放在 `app.py`
- 新增任务字段时，先定义任务级 frame，再决定内部 session 如何承接
- 不要让前端直接依赖 runtime graph 内部对象
- 如果步骤语义变化，先更新 `../../docs/orchestrator-v5-protocol.md`
- 如果中断 / 恢复语义变化，同步更新 `runtime.md`

