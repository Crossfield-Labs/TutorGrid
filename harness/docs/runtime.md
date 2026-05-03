# Runtime 模块

主要代码：
- `backend/runtime/runtime.py`
- `backend/runtime/graph.py`
- `backend/runtime/state.py`
- `backend/runtime/nodes/`
- `backend/runtime/routes/`

职责：
- 承载基于 LangGraph 的执行图
- 管理 planning、tool 执行、verification、finalize、await_user 等状态流转
- 管理 `interrupt()/resume` 的暂停与恢复点
- 优先通过 LangGraph stream 向外投影进度

关键点：
- `RuntimeState` 是 graph 内部状态，不等同于 session 对外状态
- node 要尽量小、明确、可组合
- route 负责状态跳转，不应隐藏复杂业务逻辑
- 这里是整个重构项目的核心

当前方向：
- 用真实的 LLM 规划逐步替换 bootstrap 行为
- 增加真实 tool loop、follow-up 消费、worker 委派
- 最终覆盖旧 runtime 的全部能力
- bootstrap 检查只应用在明显是项目/代码/目录分析的任务上；普通概念讲解类问题应直接回答，不要默认读仓库文件
- 当前已开始：
  - 优先走 `astream(stream_mode=["custom", "values"])`
  - `session_sync.py` 用 `get_stream_writer()` 写 `custom` 进度事件
  - `await_user` 工具在 `tools_node` 内转成 graph 级暂停，再由 `await_user_node` 调 `interrupt()`

修改时注意：
- 保持 graph state 和 session state 的分层
- 优先新增 node / route，不要重新长成一个大函数
- 新 phase 或新执行假设要同步更新本文件
- 如果调整 `interrupt/resume` 的状态语义，要同步更新 `server.md` 和 `../../docs/BackEndA/orchestrator-v5-protocol.md`

