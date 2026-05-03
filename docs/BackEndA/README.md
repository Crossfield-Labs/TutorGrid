# BackEndA 文档

这里收口后端 A 负责的编排与委派文档，不包含 RAG、知识库、画像或其他 REST 模块。

当前范围判断：
- `F04`：已完成
- `F05`：已完成
- `F12`：**后端部分已完成**
  - 已提供 `orchestrator.task.create / step / result / awaiting_user / resume / interrupt`
  - 剩余的 `/task` slash 命令、文档内任务注册卡、结果块回写属于前端接入范围

优先阅读：
- `orchestrator-v5-protocol.md`：F04 对应的任务级编排协议
- `worker-delegation.md`：F05 对应的 worker / CLI / Python Runner 委派链路
- `F04-F05-验收指南.md`：给前端与联调同学的验收清单
