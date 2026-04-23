# 当前任务与交接点

这份文档用于记录最近一轮正在推进的任务，避免状态只散落在提交和对话里。

## 当前任务主题

当前主线已经从“单纯重构旧 orchestrator”进入：

1. 让后端更像真正的学习型 Agent runtime
2. 让桌面端成为可用入口，而不是调试壳
3. 补齐记忆、压缩、整理和检索能力
4. 收口协议、学习画像、主动推送、沙箱与端到端测试
5. 补齐最小 harness 结构，让任务驱动执行、产物落盘和基础评测有统一入口

## 本轮已完成

### 1. Provider 稳定性
- `backend/providers/openai_compat.py`
- 已补：
  - 有限重试
  - 指数退避
  - 短时熔断
- 目标：
  - 避免 API/TLS 抖动时 runtime 长时间卡住

### 2. Planning 行为纠偏
- `backend/runtime/nodes/planning.py`
- 已补：
  - 普通概念讲解类问题不再默认读项目文件
  - bootstrap inspection 只对明显是项目/代码分析的任务触发

### 3. SQLite 记忆层
- `backend/memory/`
- `backend/db/`
- 已补：
  - 历史清洗
  - 会话压缩
  - 摘要 / facts / chunk 文档生成
  - SQLite 持久化
  - 本地 embedding 与相似度检索
  - 统一 ORM 基础层（SQLAlchemy）

### 4. 记忆接入 planner
- `backend/llm/planner.py`
- `backend/runtime/nodes/planning.py`
- 已补：
  - planning 前按问题检索相关历史记忆
  - 检索结果作为临时 `memory_context` 注入 planner
  - 不污染原始 planner history

### 5. 设置页升级
- `frontend/src/app/App.tsx`
- 已补：
  - 连接设置
  - 模型/API 设置
  - 记忆设置
  - Material 风格的 `Alert / LinearProgress / Switch / Select / Paper / Divider`

### 6. 运行时记忆策略设置
- `backend/config.py`
- `backend/server/protocol.py`
- `backend/server/app.py`
- 已补：
  - 是否启用记忆召回
  - 是否自动整理
  - 完成/失败后是否整理
  - 召回范围
  - 召回强度
  - 周期性整理开关和间隔

### 7. 协议与事件层收口
- `backend/server/app.py`
- `backend/server/protocol.py`
- `backend/storage/`
- `backend/db/`
- 已补：
  - `session.trace`
  - `session.messages`
  - `session.errors`
  - `session.artifacts`
  - `artifact.created/updated/removed`
  - `session.tile`

### 8. 学习画像与主动推送
- `backend/profile/`
- `backend/scheduler/`
- 已补：
  - `L1/L2/L3/L4` 学习画像
  - `learning.push.generated`
  - `learning.push.list`

### 9. Worker/Provider 扩展
- `backend/providers/registry.py`
- `backend/runners/python_runner.py`
- 已补：
  - 国产 provider alias 映射到 `openai_compat`
  - Python Runner 最小沙箱
  - workspace root 限制
  - 超时与输出截断

### 10. TipTap AI 命令后端
- `backend/editor/tiptap.py`
- `backend/server/app.py`
- 已补：
  - `orchestrator.tiptap.command`
  - 预览模式与执行模式
  - 将编辑器命令翻译成新会话任务或现有会话 follow-up

### 11. 记忆整理器
- `backend/memory/sqlite_store.py`
- `backend/memory/service.py`
- 已补：
  - `memory.cleanup`
  - 重复文档去重
  - 空文档清理

### 12. WebSocket 端到端测试
- `tests/test_websocket_e2e.py`
- `scripts/e2e_ws.py`
- 已补：
  - `start`
  - `input`
  - `snapshot`
  - `history`
  - `trace`
  - `errors`
  - `memory.compact`
  - `memory.search`
  - `interrupt`

### 14. ORM 与数据库工具
- `backend/db/`
- `backend/tools/database.py`
- `backend/tools/registry.py`
- 已补：
  - `backend/storage/sqlite_store.py`、`backend/memory/sqlite_store.py`、`backend/profile/store.py` 迁到统一 ORM 基础层
  - `query_database` 只读数据库工具，供 runtime/agent 查询持久化数据

### 13. 设置页与 Inspector 面板
- `frontend/src/app/App.tsx`
- `frontend/src/features/state-panel/StatePanel.tsx`
- 已补：
  - 设置页“立即整理记忆”按钮
  - `trace / errors / artifacts` 真实查询接入
  - Inspector 分页查看概览、trace、错误和产物

## 当前仍未完成

### P0
1. 记忆整理器
   - 现在已经有去重和空文档清理
   - 还没有：
     - 合并
     - 降级
     - 归档
     - 过期处理

### P1
2. Electron 与后端联调深度仍不足
   - 自动拉起已经有
   - 还需要继续验证打包后行为

3. 真实 CLI/SDK 联调
   - codex / claude / opencode 仍需要更完整的端到端回归

## 下一步建议

建议顺序：
1. 把记忆整理器扩到合并/归档/过期
2. 持续强化 `L3/L4` 的升级与降级策略
3. 做打包态 Electron + 内置后端的实机联调
4. 补更完整的 worker 真实环境回归

## 修改时注意

- 记忆相关改动，至少同步更新：
  - `docs/persistence.md`
  - `harness/docs/memory.md`
  - `harness/docs/gaps.md`
- 设置页相关改动，至少同步更新：
  - `harness/docs/frontend.md`
- 如果改变了“当前主线任务”，同步更新本文件
