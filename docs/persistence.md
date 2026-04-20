# 持久化模型设计

这份文档定义下一阶段要补的持久化层，用来支持：
- 历史会话恢复
- GUI 会话列表与时间线
- 错误追踪
- trace / snapshot 查询
- 上下文压缩

当前原则：
1. 先做本地单机可用版本
2. 先满足当前 WebSocket server 和 GUI 需求
3. 不让前端直接依赖 runtime 内部弱结构

## 目标

持久化层至少要承接这些对象：
- session
- message history
- followup
- tool event
- worker run
- snapshot
- error
- trace entry
- compression checkpoint

建议第一版存储：
- 主存储：SQLite
- 追加 trace：JSONL

原因：
- SQLite 足够支撑单机和开发阶段
- JSONL 适合保留原始事件轨迹和调试回放

## 数据模型

### 1. sessions

用于会话列表、历史恢复、GUI 左侧导航。

建议字段：
- `session_id`
- `task_id`
- `node_id`
- `runner`
- `workspace`
- `task`
- `goal`
- `status`
- `phase`
- `stop_reason`
- `latest_summary`
- `latest_artifact_summary`
- `permission_summary`
- `session_info_summary`
- `mcp_status_summary`
- `active_worker`
- `active_session_mode`
- `active_worker_profile`
- `active_worker_task_id`
- `active_worker_can_interrupt`
- `awaiting_input`
- `pending_user_prompt`
- `snapshot_version`
- `created_at`
- `updated_at`
- `completed_at`

说明：
- 这一层对应 `backend/sessions/state.py` 中对外可见的稳定字段
- GUI 会话列表不应该直接扫 trace 来拼这些信息

### 2. session_messages

用于恢复 planner 上下文和历史消息查看。

建议字段：
- `id`
- `session_id`
- `seq`
- `role`
- `message_type`
- `content_text`
- `content_json`
- `tool_name`
- `tool_call_id`
- `created_at`

说明：
- `message_type` 用来区分普通消息、tool call、tool result、system summary
- `content_json` 用于保留结构化工具调用原文
- 这一层替代对 `session.context["planner_messages"]` 的隐式依赖

### 3. session_followups

用于恢复 redirect / instruction / comment / reply 的排队状态。

建议字段：
- `id`
- `session_id`
- `seq`
- `intent`
- `target`
- `text`
- `status`
- `created_at`
- `consumed_at`

状态建议：
- `queued`
- `consumed`
- `dropped`

### 4. session_substeps

用于时间线中的细粒度执行记录。

建议字段：
- `id`
- `session_id`
- `seq`
- `kind`
- `title`
- `status`
- `detail`
- `created_at`

说明：
- 对应 CLI 中现在看到的 `[substep] ...`
- GUI 时间线的最小事件单元应该优先来自这里

### 5. session_tool_events

用于工具执行历史和调试。

建议字段：
- `id`
- `session_id`
- `seq`
- `tool_name`
- `phase`
- `request_json`
- `response_text`
- `response_json`
- `success`
- `created_at`

说明：
- 这一层和 `session_substeps` 有重叠，但粒度不同
- substeps 更适合 UI
- tool events 更适合恢复与调试

### 6. worker_runs

用于记录委派和外部执行器运行历史。

建议字段：
- `id`
- `session_id`
- `worker`
- `session_mode`
- `profile`
- `worker_task_id`
- `status`
- `exit_code`
- `summary`
- `artifact_summary`
- `started_at`
- `ended_at`
- `metadata_json`

### 7. session_errors

用于结构化错误持久化。

建议字段：
- `id`
- `session_id`
- `seq`
- `error_layer`
- `error_code`
- `message`
- `details_json`
- `retryable`
- `phase`
- `worker`
- `created_at`

`error_layer` 建议枚举：
- `planner`
- `tool`
- `worker`
- `transport`
- `server`
- `storage`

### 8. session_snapshots

用于历史状态回放和 GUI 时间点恢复。

建议字段：
- `id`
- `session_id`
- `snapshot_version`
- `status`
- `phase`
- `snapshot_json`
- `created_at`

说明：
- `snapshot_json` 存 `session.build_snapshot()` 的稳定输出
- 不要让 GUI 去重建历史 snapshot

### 9. session_trace_entries

用于原始事件轨迹。

建议字段：
- `id`
- `session_id`
- `event_name`
- `payload_json`
- `created_at`

说明：
- 第一版可直接沿用当前 `scratch/session-trace/*.jsonl`
- 后续可选同步写入 SQLite

### 10. compression_checkpoints

用于长会话压缩和恢复。

建议字段：
- `id`
- `session_id`
- `checkpoint_seq`
- `source_message_range`
- `summary_text`
- `summary_json`
- `token_estimate`
- `created_at`

说明：
- 这是 GUI 长历史查看和 runtime 压缩恢复的基础

## 存储接口建议

建议新增一层：
- `backend/storage/`

第一版建议文件：
- `backend/storage/__init__.py`
- `backend/storage/base.py`
- `backend/storage/sqlite_store.py`
- `backend/storage/models.py`
- `backend/storage/migrations.py`

建议暴露的接口：
- `save_session(session)`
- `list_sessions(limit, cursor)`
- `get_session(session_id)`
- `append_message(session_id, ...)`
- `append_followup(session_id, ...)`
- `append_substep(session_id, ...)`
- `append_tool_event(session_id, ...)`
- `append_worker_run(session_id, ...)`
- `append_error(session_id, ...)`
- `save_snapshot(session_id, snapshot)`
- `list_trace_entries(session_id, limit, cursor)`
- `save_compression_checkpoint(session_id, ...)`

## 与当前代码的接入点

优先接入这些位置：
- `backend/sessions/manager.py`
- `backend/server/app.py`
- `backend/runtime/runtime.py`
- `backend/runtime/session_sync.py`
- `backend/tools/delegate.py`
- `backend/workers/*.py`

建议顺序：
1. session create / update 时持久化 `sessions`
2. snapshot 广播前写 `session_snapshots`
3. substep 输出时写 `session_substeps`
4. tool 调用时写 `session_tool_events`
5. worker 委派时写 `worker_runs`
6. 报错时写 `session_errors`
7. 最后再接 `compression_checkpoints`

## 不该怎么做

1. 不要只把整个 `session.context` 原样 dump 到数据库当唯一恢复来源。
2. 不要让 GUI 通过解析 trace 拼会话列表。
3. 不要把压缩结果只存在内存里。
4. 不要先做过度通用化的 ORM 抽象。

## 第一阶段验收标准

做到以下几点就算第一阶段完成：
1. 可以列出历史 session
2. 可以加载指定 session 的最新 snapshot
3. 可以查看 session 的 substeps 和 recent trace
4. 运行失败后可以查到结构化错误
5. planner messages 可以恢复

## 记忆层补充

第一版记忆层走：
- `SQLite`
- 本地压缩后的会话摘要/事实/知识块
- 本地可重复的轻量 embedding 与相似度检索

新增建议目录：
- `backend/memory/`

第一版原则：
1. 原始 event log 不直接入向量检索
2. 先清洗、压缩、拍扁，再入记忆表
3. 先用 SQLite 保存 embedding 和文档元数据
4. 检索阶段可以先在 Python 层算相似度，不急着引入更重的外部向量库

第一版表建议：
- `memory_compactions`
  - `session_id`
  - `summary_text`
  - `facts_json`
  - `source_item_count`
  - `updated_at`
- `memory_documents`
  - `document_id`
  - `session_id`
  - `document_type`
  - `title`
  - `content`
  - `metadata_json`
  - `embedding_json`
  - `token_estimate`
  - `created_at`
  - `updated_at`

建议分级：
- `L1` 临时记忆：当前会话短期上下文，不长期入库
- `L2` 会话记忆：单个 session 的摘要、事实、关键块
- `L3` 项目记忆：同项目或同工作区复用的稳定背景
- `L4` 长期记忆：用户偏好、学习状态、长期约束

整理原则：
1. 原始 trace 只做事实来源，不直接做召回主体
2. 先去噪，再压缩，再拍扁成记忆块
3. 自动整理至少支持：
   - 会话完成后
   - 会话失败后
   - 手动触发
4. 后续应补：
   - 去重
   - 合并
   - 降级
   - 归档
   - 过期处理


