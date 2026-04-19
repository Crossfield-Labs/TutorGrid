# Orchestrator

这里已经是 PC orchestrator 的新根目录。

这个根目录 README 保持简短，只负责说明入口关系：
- 项目概览、当前范围、启动方式放在这里
- 协作规则放在 `AGENTS.md` 和 `CONTRIBUTING.md`
- 更详细的设计、协议、演进文档放在 `docs/`
- 面向 agent 的模块导航放在 `agent/`

当前范围：
- `server/`：WebSocket 入口与协议处理
- `sessions/`：会话状态与会话管理
- `runtime/`：基于 LangGraph 的运行时骨架
- `llm/`、`tools/`、`workers/`、`providers/`：执行能力栈
- `runners/`：把外部请求接入运行时
- `frontend/`：桌面应用前端（Electron + React + TypeScript）
- 下一阶段重点：`GUI + 持久化 + 上下文压缩`

快速开始：

```powershell
python -m pip install -r requirements.txt
python -m compileall .
python -m main --host 127.0.0.1 --port 3210
```

桌面应用启动方式：

```powershell
cd frontend
npm install
npm run dev
```

当前桌面前端架构：
- UI：`React + TypeScript`
- 桌面壳：`Electron`
- 后端：现阶段仍是独立运行的 Python orchestrator，本地通过 `WebSocket` 联调

配置说明：
- 用 `config.example.json` 作为本地 `config.json` 模板
- `config.json` 已被 Git 忽略
- 环境变量仍然可以覆盖文件配置

文档入口：
- 协作方式：`CONTRIBUTING.md`
- agent 接手入口：`AGENTS.md`
- 详细项目文档：`docs/README.md`
- GUI 与下一阶段路线：`docs/roadmap.md`
- agent 模块导航：`agent/README.md`

