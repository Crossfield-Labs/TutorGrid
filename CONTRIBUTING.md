# 协作说明

当前仓库根目录已经是新的独立系统实现。

基本规则：
- 新实现直接落在当前根目录模块内
- `README.md` 是给人看的根入口
- `AGENTS.md` 是给 agent 看的根入口
- 详细架构和长文档放在 `docs/`
- 模块边界、运行方式、测试路径变化时，要同步更新 `agent/*.md`

推荐协作流程：
1. 先读 `README.md`
2. 再读 `AGENTS.md`
3. 再读 `agent/` 下对应模块文档
4. 完成代码改动
5. 如果行为变化了，同时更新 `agent/` 或 `docs/`
6. 至少做一轮最小本地验证

最小验证基线：
- `python -m compileall orchestrator`
- `python -m dev.run_runtime "test task" --workspace <workspace>`
- 如果改了协议或会话流程，再跑 WebSocket 路径

文档分层：
- 根目录文档：入口、协作方式、短说明
- `docs/`：详细设计、人类长期维护文档
- `agent/`：给 agent 快速定位模块和约束的文档

Agent 接手时，先从 `AGENTS.md` 开始，再进入 `agent/README.md`。

