# 当前任务与交接点

这份文档用于记录最近一轮正在推进的任务，避免状态只散落在提交和对话里。

## 当前任务主题

当前主线已经从“单纯重构旧 orchestrator”进入：

1. 让后端更像真正的学习型 Agent runtime
2. 让桌面端成为可用入口，而不是调试壳
3. 补齐记忆、压缩、整理和检索能力

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
- 已补：
  - 历史清洗
  - 会话压缩
  - 摘要 / facts / chunk 文档生成
  - SQLite 持久化
  - 本地 embedding 与相似度检索

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

## 当前仍未完成

### P0
1. 长短期记忆真正分层
   - 现在主要还是 session 级记忆
   - 还没形成项目级和长期级记忆升级逻辑

2. 记忆整理器
   - 现在有自动 compact 触发
   - 还没有：
     - 去重
     - 合并
     - 降级
     - 归档
     - 过期处理

3. GUI 错误与 trace
   - 还缺：
     - 错误详情
     - trace 拉取
     - artifact 面板

### P1
4. Electron 与后端联调深度仍不足
   - 自动拉起已经有
   - 还需要继续验证打包后行为

5. 真实 CLI/SDK 联调
   - codex / claude / opencode 仍需要更完整的端到端回归

## 下一步建议

建议顺序：
1. 做 `L3/L4` 记忆升级逻辑
2. 做记忆整理器（去重/合并/归档）
3. 给设置页补“立即整理一次记忆”
4. 补 `trace / errors / artifacts` GUI 面板

## 修改时注意

- 记忆相关改动，至少同步更新：
  - `docs/persistence.md`
  - `agent/memory.md`
  - `agent/gaps.md`
- 设置页相关改动，至少同步更新：
  - `agent/frontend.md`
- 如果改变了“当前主线任务”，同步更新本文件
