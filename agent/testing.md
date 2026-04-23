# 测试说明

当前主要验证路径：
- `python -m compileall backend tests`
- `python -m backend.dev.run_runtime "task" --workspace <workspace>`
- `python -m backend.main --host 127.0.0.1 --port 3210`
- `python -m unittest tests.test_websocket_e2e -v`
- `python scripts/e2e_ws.py --ws-url ws://127.0.0.1:3210/ws/orchestrator`
- 如果要验证真实委派，先确认本机可执行：
  - `codex`
  - `claude`
  - `opencode`

测试分层：
- 静态导入与编译检查
- 直接 runtime 执行检查
- WebSocket 协议检查
- worker 集成、interrupt、follow-up 检查
- 手动端到端脚本检查

当前最值得补的集成测试：
- `delegate_task` 触发后 session 是否更新 `activeWorker`、`workerRuns`、`artifacts`
- server 是否按 snapshot 变化广播 `phase/worker/summary/artifact_summary`
- `interrupt` 和 `snapshot` 在运行中是否能拿到一致状态

当前 WebSocket 端到端覆盖：
- `orchestrator.session.start`
- `orchestrator.session.input`
- `orchestrator.session.snapshot`
- `orchestrator.session.history`
- trace 文件写入与读取
- 错误会话在 history 中的 `error` 项
- `orchestrator.memory.compact`
- `orchestrator.memory.search`
- `orchestrator.session.interrupt`

新增测试时：
- runtime 相关测试优先放到 `tests/`
- backend/server + backend/sessions 变化时补协议覆盖
- 新验证路径出现时，同步更新这里



