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
  - `orchestrator.session.input`
  - `orchestrator.session.snapshot`
  - `orchestrator.session.cancel`
  - `orchestrator.session.interrupt`
- 当前已投影的主要事件：
  - `orchestrator.session.progress`
  - `orchestrator.session.phase`
  - `orchestrator.session.worker`
  - `orchestrator.session.summary`
  - `orchestrator.session.artifact_summary`
  - `orchestrator.session.permission`
  - `orchestrator.session.mcp_status`
  - `orchestrator.session.worker_runtime`
  - `orchestrator.session.snapshot`

修改时注意：
- 请求解析放在 `protocol.py`
- 订阅、广播、连接行为放在 `app.py`
- 新消息类型要同步反映到 snapshot 和广播逻辑
- `session.build_snapshot()` 是投影事件的单一事实来源，新增状态字段时先补 snapshot，再补广播
- 当前桌面 GUI 已依赖：
  - 会话列表
  - 历史时间线
  - snapshot 详情
- 下一阶段会继续补 trace 和错误查询，详见 `../docs/gui-protocol.md`

