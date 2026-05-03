# Workers 模块

主要代码：
- `backend/workers/base.py`
- `backend/workers/registry.py`
- `backend/workers/codex_worker.py`
- `backend/workers/opencode_worker.py`
- `backend/workers/common.py`
- `backend/tools/delegate.py`

职责：
- 作为统一接口下的委派执行后端。
- 把 runtime 的委派请求落到真实 CLI。
- 向 session/runtime 回传进度、产物和执行结果。

当前可用 worker：
- `codex`
- `opencode`

Claude 状态：
- Claude 在当前构建中被禁用。
- `WorkerRegistry` 只注册 `codex` 和 `opencode`。
- `RunnerRouter` 不再暴露 `claude_cli`。
- `claude_runner.py` / `claude_worker.py` 仅保留历史代码入口，`run()` 会直接报错，不会启动 Claude。
- planner prompt 和 `delegate_task` 工具描述不再推荐 Claude。

关键点：
- worker 是执行适配器，不是 orchestration owner。
- 是否委派由 runtime/planner 决定。
- registry 会根据 `config.enabled_workers` 过滤可用 worker，但只允许 `codex` / `opencode` 生效。
- `backend/workers/common.py` 负责命令解析、工作区快照、产物 diff、stdout/stderr 流式进度回传。
- `backend/runners/python_runner.py` 提供受限 Python runner，只能在受限工作目录下运行，带超时、输出截断和环境变量白名单。
- `python_runner` 现在还会把本次执行生成的 artifact diff 和记到 `session.worker_runs`，并通过 `orchestrator.task.result` 暴露给前端。
- F05 相关设计与验收文档已收口到 `../../docs/BackEndA/worker-delegation.md`。

修改时注意：
- session、progress、artifact 和 worker result 结构要保持对前端稳定。
- 不要让 Python runner 变成任意命令执行器。
- 不要在调度器路径中重新启用 Claude，除非项目明确恢复该安全边界。
- 如果改了 CLI 参数、输出格式或 progress 翻译方式，要同步更新测试。
