# Workers 模块

主要代码：
- `workers/base.py`
- `workers/registry.py`
- `workers/codex_worker.py`
- `workers/claude_worker.py`
- `workers/opencode_worker.py`

职责：
- 作为统一接口下的委派执行后端
- 负责把 runtime 的委派请求落到真实 CLI 或 SDK
- 向 session/runtime 回传进度、产物和执行结果

关键点：
- worker 是执行适配器，不是 orchestration owner
- 何时委派由 runtime 决定
- worker registry 要保持声明式、易读
- 当前 registry 会根据 `config.enabled_workers` 过滤可用 worker

当前状态：
- `codex_worker.py`、`opencode_worker.py` 已接到本地 CLI
- `claude_worker.py` 已切到 Claude Agent SDK 路径，支持 profile、session mode、hook、MCP 状态、session introspection、control ref
- `workers/common.py` 负责命令解析、工作区快照、产物 diff、stdout/stderr 流式进度回传
- `workers/claude_sdk_bridge.py` 负责把 Claude SDK 消息翻译成统一的 `WorkerProgressEvent`
- 当前剩余风险主要在本机环境依赖：
  - 需要安装 `claude-agent-sdk`
  - 需要本机 `claude` CLI / settings / MCP 配置正确

修改时注意：
- 让 session、progress、结果结构保持对未来 runtime 友好
- 遇到非平凡后端假设时，补进这份文档
- 如果改了 CLI 参数、输出格式或 progress 翻译方式，要同步更新测试说明
