# Orchestrator

这里已经是 PC orchestrator 的新根目录。

这个根目录 README 保持简短，只负责说明入口关系：
- 项目概览、当前范围、启动方式放在这里
- 协作规则放在 [AGENTS.md](./AGENTS.md) 和 [CONTRIBUTING.md](./CONTRIBUTING.md)
- 更详细的设计、协议、演进文档放在 [docs/](docs/)
- 面向 agent 的模块导航与 harness 入口放在 [harness/](harness/)

当前范围：
- `backend/server/`：HTTP / SSE / WebSocket 协议入口
- `backend/sessions/`：会话状态与会话管理
- `backend/runtime/`：基于 LangGraph 的运行时骨架
- `backend/db/`、`backend/storage/`、`backend/memory/`：ORM 持久化、会话存储与记忆层
- `backend/llm/`、`backend/tools/`、`backend/workers/`、`backend/providers/`：执行能力栈
- `backend/runners/`：把外部请求接入运行时
- `harness/`：任务定义、统一执行入口、结果产物与基础评测
- `TutorGridFront/`：桌面应用前端（Electron + Vue 3 + TypeScript + Vuetify）
- 下一阶段重点：`GUI + 持久化 + 上下文压缩`

快速开始：

```powershell
python -m pip install -r requirements.txt
python -m compileall .
```

桌面应用启动方式：

```powershell
cd TutorGridFront
yarn install
yarn electron:dev
```

当前桌面前端架构：
- UI：`Vue 3 + TypeScript + Vuetify`
- 桌面壳：`Electron`
- 后端：位于 `backend/`，当前桌面前端通过 `SSE + REST` 联调，并在 Electron 启动时自动拉起本地 `FastAPI` 后端（默认 `http://127.0.0.1:8000`）

配置说明：
- 用 `config.example.json` 作为本地 `config.json` 模板
- `config.json` 位于仓库根目录，已被 Git 忽略
- 环境变量仍然可以覆盖文件配置

文档入口：
- 协作方式：[CONTRIBUTING.md](./CONTRIBUTING.md)
- agent 接手入口：[AGENTS.md](./AGENTS.md)
- 详细项目文档：[docs/README.md](docs/README.md)
- V5 编排协议：[docs/orchestrator-v5-protocol.md](docs/orchestrator-v5-protocol.md)
- Harness 说明：[docs/harness.md](docs/harness.md)
- harness 模块导航：[harness/docs/README.md](harness/docs/README.md)


