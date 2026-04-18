# Runtime 模块

主要代码：
- `runtime/runtime.py`
- `runtime/graph.py`
- `runtime/state.py`
- `runtime/nodes/`
- `runtime/routes/`

职责：
- 承载基于 LangGraph 的执行图
- 管理 planning、tool 执行、verification、finalize、await_user 等状态流转

关键点：
- `RuntimeState` 是 graph 内部状态，不等同于 session 对外状态
- node 要尽量小、明确、可组合
- route 负责状态跳转，不应隐藏复杂业务逻辑
- 这里是整个重构项目的核心

当前方向：
- 用真实的 LLM 规划逐步替换 bootstrap 行为
- 增加真实 tool loop、follow-up 消费、worker 委派
- 最终覆盖旧 runtime 的全部能力

修改时注意：
- 保持 graph state 和 session state 的分层
- 优先新增 node / route，不要重新长成一个大函数
- 新 phase 或新执行假设要同步更新本文件
