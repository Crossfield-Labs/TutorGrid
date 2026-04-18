# 测试说明

当前主要验证路径：
- `python -m compileall orchestrator`
- `python -m orchestrator.dev.run_runtime "task" --workspace <workspace>`
- `python -m orchestrator.main --host 127.0.0.1 --port 3210`

测试分层：
- 静态导入与编译检查
- 直接 runtime 执行检查
- WebSocket 协议检查
- 后续 worker 集成、interrupt、follow-up 检查

新增测试时：
- runtime 相关测试优先放到 `orchestrator/tests/`
- server/session 变化时补协议覆盖
- 新验证路径出现时，同步更新这里
