# Sessions 模块

主要代码：
- `backend/sessions/state.py`
- `backend/sessions/manager.py`

职责：
- 表达对外可见的 session 状态
- 保存 status、phase、prompt、artifacts、follow-ups、snapshot 等信息
- 提供内存态 session 注册表

关键点：
- `OrchestratorSessionState` 是面向传输层的状态模型
- snapshot 字段要与 server 广播事件保持一致
- follow-up 和等待用户输入状态应该在这里收敛，不要散落在全局变量里
- 下一阶段要把当前内存态 session 投影到持久化层，详见 `../docs/persistence.md`
- GUI 依赖的稳定任务投影字段也要从这里继续补，详见 `../../docs/BackEndA/orchestrator-v5-protocol.md`

修改时注意：
- 新状态字段要谨慎增加
- 只要字段影响客户端可见行为，就要更新 snapshot 输出
- manager 保持小而纯，主要做状态管理
- 不要继续扩大对 `session.context` 的隐式依赖，能变成显式字段或持久化模型的要逐步抽出来

