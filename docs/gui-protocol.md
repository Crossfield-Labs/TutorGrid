# GUI 协议说明

旧的 GUI 会话协议文档已经退役。

原因：
- V5 编排前端不再以 `orchestrator.session.*` 作为主契约继续扩展
- F04 的主接口已经切到任务级协议

请改读：
- [BackEndA/orchestrator-v5-protocol.md](./BackEndA/orchestrator-v5-protocol.md)

说明：
- 本文件只保留为兼容入口，避免旧链接失效
- RAG、Chat SSE、知识库相关接口不在这里迁移
- 旧 `orchestrator.session.*` 仅作为内部适配与回归验证通道，不再作为新前端编排接口文档维护

