# Server 模块

主要代码：
- `backend/server/app.py`
- `backend/server/protocol.py`

职责：
- 暴露独立 WebSocket 服务
- 接收 session 生命周期请求
- 广播进度、阶段、worker、摘要、快照、完成与失败事件

关键点：
- 当前 socket 路径是 `/ws/orchestrator`
- token 校验在 WebSocket 入口完成
- server 暴露的方法应与 runtime 真正支持的能力保持一致
- 当前已支持的主要方法：
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
  - `orchestrator.tiptap.command`
  - `orchestrator.memory.cleanup`
  - `orchestrator.memory.compact`
  - `orchestrator.memory.search`
  - `orchestrator.memory.reindex`
  - `orchestrator.profile.get`
  - `orchestrator.profile.l1.set`
  - `orchestrator.profile.l2.list`
  - `orchestrator.profile.l2.upsert`
  - `orchestrator.profile.l4.list`
  - `orchestrator.profile.l4.upsert`
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
  - `orchestrator.learning.push.list`
- 当前已投影的主要事件：
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

修改时注意：
- 请求解析放在 `protocol.py`
- 订阅、广播、连接行为放在 `app.py`
- 新消息类型要同步反映到 snapshot 和广播逻辑
- `session.build_snapshot()` 是投影事件的单一事实来源，新增状态字段时先补 snapshot，再补广播
- 当前 event frame 统一带 `timestamp`，session 广播事件额外带 `seq`
- 当前桌面 GUI 已依赖：
  - 会话列表
  - 历史时间线
  - snapshot 详情
- 编辑器侧命令通过 `orchestrator.tiptap.command` 进入后端，支持预览和执行两种模式
- 记忆整理支持自动触发和 `orchestrator.memory.cleanup` 手动触发
- 知识库与学习画像接口也挂在同一条 WebSocket 协议面上，新增字段时先补 `protocol.py` 的参数解析

