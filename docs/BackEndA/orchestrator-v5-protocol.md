# Orchestrator V5 编排协议

这份文档只覆盖 V5 的编排部分，对应任务书 `F04`，并作为 `F12` 的后端协议基础。

不在本文档范围内的内容：
- Chat SSE
- RAG / 知识库
- 学习画像
- 其他 REST CRUD
- TipTap 前端 `/task` slash 命令本身的 UI 接入
- 文档内 `task_register / task_result` 节点渲染

## 目标

V5 的编排接口不再以“GUI 会话调试协议”为主，而是以“文档内注册任务”作为对前端暴露的主契约。

当前约束：
- 保留现有 LangGraph 骨架：`planning -> tools -> verify -> finalize`
- 对外主入口收敛到任务级协议
- 支持步骤级流式推送
- 支持中断与恢复
- 后续流式实现统一按 `version="v2"` 收口

## 与 F12 的关系

`F12` 是“Slash 命令 `/task` → 注册编排任务”的前后端协作项。

其中后端 A 的交付范围是：
- 接收 `/task` 最终发出的 `orchestrator.task.create`
- 驱动编排执行
- 推送 `task.step / task.awaiting_user / task.result`
- 支持 `task.resume / task.interrupt`

当前判断：
- **F12 后端部分已完成**
- 前端文档内 `/task` 命令、任务注册卡、结果块回写不在本文档覆盖范围内

## 通道

编排仍使用 WebSocket：

```text
WS /ws/orchestrator
```

帧结构保持请求 / 响应 / 事件三类：

```json
{
  "type": "request",
  "id": "req_001",
  "method": "orchestrator.task.create",
  "params": {}
}
```

```json
{
  "type": "response",
  "id": "req_001",
  "ok": true,
  "data": {}
}
```

```json
{
  "type": "event",
  "event": "orchestrator.task.step",
  "timestamp": "2026-05-02T12:00:00Z",
  "data": {}
}
```

## 核心方法

### 1. `orchestrator.task.create`

用途：
- 从文档内注册一个新的编排任务
- 由后端负责把任务投影到现有 runtime / session 执行链

请求：

```json
{
  "type": "request",
  "id": "req_task_create_001",
  "method": "orchestrator.task.create",
  "params": {
    "session_id": "sess_xxx",
    "doc_id": "hyper_001",
    "instruction": "帮我用 sklearn 跑一个线性回归 demo",
    "context": {
      "recent_doc_content": "这里是文档里最近一段内容"
    }
  }
}
```

字段说明：
- `session_id`：前端当前文档会话标识
- `doc_id`：文档标识
- `instruction`：用户在文档内注册的任务文本
- `context`：可选上下文，仅用于补充任务语义

工作区约定：
- 如果前端没有显式传 `params.workspace`，后端默认把本次任务工作区创建在 `scratch/tasks/<task_id>/`
- 任务运行过程中生成的脚本、图片、临时文件、产物索引都应优先落在该任务目录下
- 只有前端或调用方明确指定 `workspace` 时，才覆盖这一默认目录

成功响应：

```json
{
  "type": "response",
  "id": "req_task_create_001",
  "ok": true,
  "data": {
    "task_id": "task_001",
    "session_id": "sess_xxx",
    "doc_id": "hyper_001",
    "status": "pending"
  }
}
```

### 2. `orchestrator.task.resume`

用途：
- 恢复一个因 `interrupt()` 或等待用户输入而暂停的任务

请求：

```json
{
  "type": "request",
  "id": "req_task_resume_001",
  "method": "orchestrator.task.resume",
  "params": {
    "task_id": "task_001",
    "session_id": "sess_xxx",
    "input": {
      "kind": "reply",
      "content": "继续，使用本地 CSV 数据"
    }
  }
}
```

### 3. `orchestrator.task.interrupt`

用途：
- 主动中断正在执行的编排任务

请求：

```json
{
  "type": "request",
  "id": "req_task_interrupt_001",
  "method": "orchestrator.task.interrupt",
  "params": {
    "task_id": "task_001",
    "session_id": "sess_xxx"
  }
}
```

## 核心事件

### 1. `orchestrator.task.step`

用途：
- 推送步骤级状态变化
- 这是前端进度条、步骤列表、状态标签的主要数据源

事件：

```json
{
  "type": "event",
  "event": "orchestrator.task.step",
  "timestamp": "2026-05-02T12:00:00Z",
  "data": {
    "task_id": "task_001",
    "session_id": "sess_xxx",
    "doc_id": "hyper_001",
    "step_index": 2,
    "step_total": 4,
    "step_name": "执行代码",
    "phase": "tools",
    "status": "running",
    "summary": "正在运行 sklearn 线性回归",
    "awaiting_user": false,
    "active_worker": "opencode",
    "active_session_mode": "new",
    "active_worker_profile": "default",
    "active_worker_task_id": "worker_task_001"
  }
}
```

约定：
- `status` 枚举：`pending | running | done | failed | awaiting_user | interrupted`
- `phase` 与 runtime 内部节点对应，但前端只消费稳定字符串，不依赖内部状态对象
- `summary` 面向用户展示，不要求暴露内部 trace
- `active_worker / active_session_mode / active_worker_profile / active_worker_task_id`
  用于前端详情页展示当前委派到的第三方执行后端

### 2. `orchestrator.task.result`

用途：
- 任务结束后回传最终结果
- 前端据此回写文档、展示产物、更新消息流

事件：

```json
{
  "type": "event",
  "event": "orchestrator.task.result",
  "timestamp": "2026-05-02T12:00:10Z",
  "data": {
    "task_id": "task_001",
    "session_id": "sess_xxx",
    "doc_id": "hyper_001",
    "status": "done",
    "result_type": "code_output",
    "content": "✅ R² = 0.94\n拟合图已生成",
    "artifacts": [
      {
        "type": "image",
        "path": "data/artifacts/plot_001.png"
      },
      {
        "type": "code",
        "language": "python",
        "content": "from sklearn.linear_model import LinearRegression"
      }
    ],
    "worker_runs": [
      {
        "worker": "python_runner",
        "success": true,
        "summary": "coef=1.98 ... R2=0.94",
        "output": "coef=1.98\nintercept=0.13\nR2=0.94\nartifact=sklearn_linear_regression.png",
        "metadata": {
          "workspace": "scratch/tasks/task_001",
          "python_command": "python"
        }
      }
    ]
  }
}
```

失败时：
- `status` 为 `failed`
- `content` 应给出面向用户的失败说明
- 可选补 `error_code`
- 如经过 `codex / opencode / python_runner` 等第三方执行后端，
  `worker_runs` 会带回本次执行摘要、输出、artifact 和 fallback 元数据

### 3. `orchestrator.task.awaiting_user`

用途：
- 显式告诉前端当前任务需要用户补充输入
- 这是 `interrupt()` / `resume` 交互的外部可见投影

事件：

```json
{
  "type": "event",
  "event": "orchestrator.task.awaiting_user",
  "timestamp": "2026-05-02T12:00:05Z",
  "data": {
    "task_id": "task_001",
    "session_id": "sess_xxx",
    "doc_id": "hyper_001",
    "prompt": "请选择要使用的数据源",
    "resume_method": "orchestrator.task.resume"
  }
}
```

## 前端最小消费模型

前端只需要稳定消费以下字段：
- `task_id`
- `session_id`
- `doc_id`
- `step_index`
- `step_total`
- `step_name`
- `phase`
- `status`
- `summary`
- `content`
- `artifacts`
- `worker_runs`
- `active_worker`

前端不应该直接依赖：
- runtime graph 内部 state
- worker 私有 metadata
- session 内部临时上下文字段

## 与现有后端的适配关系

F04 不是重写 runtime，而是在现有后端基础上做协议适配。

建议分层：

1. 内部执行层
   - 继续使用现有 `runtime`
   - 继续保留 `planning -> tools -> verify -> finalize`

2. 会话状态层
   - 继续由 `sessions` 保存运行状态、等待输入、产物和快照

3. 协议投影层
   - 在 `backend/server/` 新增 V5 任务协议映射
   - 把旧的 `session` 级状态投影成新的 `task` 级事件

映射原则：
- `session.start` 的内部启动过程，对外收敛到 `task.create`
- `phase / summary / worker` 等内部变化，对外聚合为 `task.step`
- 完成 / 失败 / 产物，对外收敛为 `task.result`
- 等待用户输入状态，对外投影为 `task.awaiting_user`

## 兼容策略

当前仓库里仍然存在旧的 `orchestrator.session.*` 协议与文档，那是历史调试契约，不再作为 V5 前端主协议继续扩展。

后续策略：
- 新前端编排入口只对接 `orchestrator.task.*`
- 旧 `session` 方法仅作为内部适配与回归验证通道
- 新增字段、状态和交互，优先补到 `task` 协议，不再优先补到旧 GUI 会话协议

## 代码落点

协议与投影主要落在：
- `backend/server/app.py`
- `backend/server/protocol.py`
- `backend/sessions/`
- `backend/runtime/`

文档同步要求：
- 如果 `task.create / task.step / task.result` 的帧结构变化，先更新本文档
- 如果运行阶段或中断恢复语义变化，同步更新 `harness/docs/server.md` 和 `harness/docs/runtime.md`
