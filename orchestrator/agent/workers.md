# Workers 模块

主要代码：
- `workers/base.py`
- `workers/registry.py`
- `workers/codex_worker.py`
- `workers/claude_worker.py`
- `workers/opencode_worker.py`

职责：
- 作为统一接口下的委派执行后端
- 为后续真实 worker-backed 执行做准备

关键点：
- worker 是执行适配器，不是 orchestration owner
- 何时委派由 runtime 决定
- worker registry 要保持声明式、易读

当前状态：
- 现在还是 placeholder
- 长期目标是覆盖旧 worker 层的能力

修改时注意：
- 让 session、progress、结果结构保持对未来 runtime 友好
- 遇到非平凡后端假设时，补进这份文档
