# 文档目录

`docs/` 用来放更详细的人类文档。

适合放在这里的内容：
- 架构设计说明
- 协议设计
- runtime 执行模型
- tools / workers / providers 的详细设计
- 重构路线图和迁移记录
- GUI / TUI 产品路线与前后端协作约束

根目录的 `README.md`、`AGENTS.md`、`CONTRIBUTING.md` 应该保持短小，详细内容统一沉淀到这里。

当前优先阅读：
- `persistence.md`：session / message / snapshot / error / trace 的持久化模型
- `orchestrator-v5-protocol.md`：V5 编排任务协议与任务级事件模型
- `gui-protocol.md`：旧 GUI 会话协议的兼容入口，实际编排请改读 V5 协议
- `harness.md`：任务定义、统一执行入口、结果产物和基础评测
- `知识库_RAG_记忆_操作手册.md`：知识库/RAG/记忆从启动到联调测试的完整步骤
- `前端_知识库_RAG_记忆_详细测试文档.md`：前端联调测试清单（操作/输入/输出/期望）
- `kb-rag-memory-config.md`：Knowledge/RAG/Memory/LangSmith 相关环境变量与运行时配置字段

