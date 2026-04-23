# Memory 模块

主要代码：
- `backend/db/`
- `backend/memory/compression.py`
- `backend/memory/embedding.py`
- `backend/memory/models.py`
- `backend/memory/service.py`
- `backend/memory/sqlite_store.py`

职责：
- 清洗已有会话历史
- 生成会话摘要、关键事实和可检索知识块
- 将压缩后的高价值内容写入 SQLite 记忆表
- 提供本地相似度检索入口
- 提供最小可用的记忆整理入口

关键点：
- 原始 trace 不直接进向量检索
- 先清洗噪音，再压缩，再拍扁成文档块
- 第一版 embedding 是本地可重复的轻量实现，用来打通链路
- `memory.search` 现在是 SQLite 持久化 + Python 层相似度计算
- `memory.cleanup` 会清理重复文档和空文档，作为周期性整理基础
- 当前 SQLite 层已迁到统一 SQLAlchemy ORM 基础层，不再继续扩 raw SQL
- 学习画像现在已升级到 `L1/L2/L3/L4`
  - `L2`：单次会话/任务记忆
  - `L3`：项目或工作区稳定记忆
  - `L4`：长期学习记忆

当前方向：
- 已支撑历史会话压缩、召回和 planner 注入
- 已支撑自动整理和手动 `memory.cleanup`
- 已支撑 `L3/L4` 项目/长期记忆升级
- 下一阶段重点是扩充整理器的合并、降级、归档和过期策略

修改时注意：
- 不要把运行中的所有中间步骤直接塞进记忆层
- 新的记忆文档类型要同步更新本文件和 `docs/persistence.md`
- 如果检索策略变化，需要同步更新 `harness/docs/gaps.md`
