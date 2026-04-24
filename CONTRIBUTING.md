# 协作说明

当前仓库根目录已经是新的独立系统实现。

基本规则：
- 后端实现统一落在 `backend/`
- 前端实现统一落在 `frontend/`
- `README.md` 是给人看的根入口
- `AGENTS.md` 是给 agent 看的根入口
- 详细架构和长文档放在 `docs/`
- 模块边界、运行方式、测试路径变化时，要同步更新 `harness/docs/*.md`

推荐协作流程：
1. 先读 [README.md](./README.md)
2. 再读 [AGENTS.md](./AGENTS.md)
3. 再读 `harness/docs/` 下对应模块文档
4. 完成代码改动
5. 如果行为变化了，同时更新 `harness/docs/` 或 `docs/`
6. 至少做一轮最小本地验证

最小验证基线：
- `python -m compileall backend tests`
- `python -m backend.dev.run_runtime "test task" --workspace <workspace>`
- `python -m backend.main --host 127.0.0.1 --port 3210`
- 如果改了协议或会话流程，再跑桌面前端和 WebSocket 路径

CI 约定：
- 常规质量检查、文档检查、后端测试、harness smoke、frontend build、release 打包分成独立 workflow
- `tests/` 已进入 CI，但不再只靠单个 `discover` job；按模块拆成多组 job，便于定位失败归属
- 改动 `frontend/` 时，至少保证前端构建链路可过
- 改动 `harness/`、协议或 WebSocket 行为时，至少保证 harness smoke 路径可过

文档分层：
- 根目录文档：入口、协作方式、短说明
- `docs/`：详细设计、人类长期维护文档
- `harness/`：任务执行入口与代码
- `harness/docs/`：给 agent 快速定位模块、任务和约束的文档

Agent 接手时，先从 [AGENTS.md](./AGENTS.md) 开始，再进入 [harness/docs/README.md](harness/docs/README.md)。


