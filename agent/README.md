# Agent 文档导航

这个目录是给 agent 看的模块导航层，目标是让 agent 在接手代码前更快定位结构和边界。

建议阅读路径：
1. `../README.md`
2. `../AGENTS.md`
3. 进入本目录读取对应模块文档

模块文档：
- `gaps.md`：当前剩余缺口、优先级、LangGraph 与 LangChain 的职责边界
- `server.md`：WebSocket 入口、请求生命周期、对外协议
- `sessions.md`：会话字段、snapshot 结构、follow-up 处理
- `runners.md`：runner 抽象以及如何接入 runtime
- `runtime.md`：LangGraph runtime、节点、路由、执行目标
- `llm.md`：LangChain prompt / message 层与 planner 职责
- `providers.md`：模型 provider 抽象与 API 兼容层
- `tools.md`：tool 注册、tool 边界、tool 调用形态
- `workers.md`：worker 职责与后续委派方向
- `testing.md`：本地验证路径和测试分层
- `deprecated.md`：当前存在但不建议继续扩展的目录

连续开发建议：
1. 先读 `gaps.md`，明确当前还没补齐的行为缺口
2. 再读对应模块文档，定位代码入口
3. 修改后同步回写 `gaps.md` 的状态，避免下一个接手者重复判断

当新的顶层模块变得重要时，要把它补进这个导航文件。
