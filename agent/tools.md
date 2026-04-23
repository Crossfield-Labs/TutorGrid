# Tools 模块

主要代码：
- `backend/tools/registry.py`
- `backend/tools/database.py`
- `backend/tools/filesystem.py`
- `backend/tools/shell.py`
- `backend/tools/web.py`
- `backend/tools/user_prompt.py`
- `backend/tools/delegate.py`

职责：
- 以 LangChain 兼容形式暴露 runtime 工具
- 保持具体工具实现独立、可组合

关键点：
- tool 注册要集中
- filesystem、shell、web、user prompt、delegate、database 各自保持可测试
- runtime 应关注 tool 元数据与结果，而不是工具内部细节
- `query_database` 只允许访问受控的持久化表视图，不应暴露任意 SQL 执行

修改时注意：
- 一旦对 planner/runtime 暴露过的 tool 名称稳定下来，就不要随意改
- tool 复杂度上升时要尽早补参数校验
- 新增 tool 后，要同步更新本文件和 `agent/README.md`

