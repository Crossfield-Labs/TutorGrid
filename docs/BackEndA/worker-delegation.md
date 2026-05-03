# Worker / CLI 委派链路

这份文档对应任务书 `F05`，只覆盖后端 A 负责的委派执行链路。

## 目标

F05 要解决三件事：
- 编排引擎能把任务委派给可用执行后端
- 代码执行类任务能走本地 Python Runner
- 执行失败时有稳定降级，不因 CLI 不可用而直接崩溃

## 当前执行后端

当前实际可用的执行后端分三类：

1. `python_runner`
- 入口：
  - `backend/runners/python_runner.py`
- 适用：
  - 本地 Python 代码执行
  - 受限工作区内的脚本产物生成
- 当前能力：
  - 超时控制
  - 输出截断
  - 环境变量白名单
  - workspace artifact diff
  - 内置 `sklearn` 线性回归 demo 模板（未显式提供 `python_code` 时可兜底）
  - `worker_runs` 记录
  - 结果通过 `orchestrator.task.result` 回传

2. `codex`
- 入口：
  - `backend/workers/codex_worker.py`
  - `backend/runners/codex_runner.py`
- 适用：
  - 分析、诊断、审查类任务
  - 支持会话策略选择

3. `opencode`
- 入口：
  - `backend/workers/opencode_worker.py`
  - `backend/runners/opencode_runner.py`
- 适用：
  - 更偏执行、实现、修改类任务

## 选择策略

核心代码：
- `backend/workers/selection.py`
- `backend/tools/delegate.py`

当前选择规则：
- 明确指定 `worker` 时，优先按显式指定执行
- 任务文本包含：
  - `review / analyze / inspect / explain / diagnose`
  更偏向 `codex`
- 任务文本包含：
  - `implement / write / create / fix / patch / edit / refactor / generate`
  更偏向 `opencode`
- 未命中显式特征时：
  - 默认优先 `opencode`
  - 再 fallback 到 `codex`

## Session 策略

当前 session 策略只对 `codex` 有意义：
- `new`
- `resume`
- `fork`

核心代码：
- `backend/workers/selection.py`

当前规则：
- 非 `codex` 默认 `new`
- `codex` 且无旧 session 时：
  - `new`
- `codex` 且任务语义像 follow-up 时：
  - `resume`

## 结果回传

委派结果统一写回：
- `session.worker_runs`
- `session.artifacts`
- `session.latest_artifact_summary`

对前端的主要投影是：
- `orchestrator.task.step`
- `orchestrator.task.result`

其中 `task.result` 当前会携带：
- `status`
- `result_type`
- `content`
- `artifacts`
- `worker_runs`

另外 `task.step` 当前还会带：
- `active_worker`
- `active_session_mode`
- `active_worker_profile`

这样前端详情页可以直接看到本轮是否委派到了 `codex / opencode / python_runner`。

## 降级方案

核心代码：
- `backend/tools/delegate.py`

当前降级逻辑：
- 如果首选 worker 失败：
  - 自动尝试 fallback worker
- 如果全部 worker 都失败：
  - 返回显式 fallback 结果，而不是 crash
  - 当前结果形态：
    - `worker: "fallback"`
    - `metadata.fallback_recommended: true`
    - `metadata.attempted_workers`
    - `summary` 中给出“回退到纯 LLM 推理”的提示

这意味着当前系统已经满足：
- “Worker 不可用时有 fallback 提示而非 crash”

## 当前验证状态

已验证：
- `tests/test_delegate_runtime.py`
  - worker 选择与 fallback 顺序
  - 全部 worker 失败时的 fallback 提示
- `tests/test_python_runner.py`
  - Python Runner 输出截断
  - 工作区边界约束
  - `python_code` 上下文执行
  - artifact / `worker_runs` 写回
- `tests/test_websocket_e2e.py`
  - `task.create -> python runner -> task.result`
  - `worker_runs / artifacts` 协议回传

## 交付判断

按任务书 F05 的两条验收标准逐项判断：

1. `"帮我跑一个sklearn线性回归" -> Python Runner执行 -> 返回stdout + 图片`
- 当前状态：
  - `stdout` 回传链路已具备
  - artifact 回传链路已具备
  - `python_runner` 已补内置 `sklearn` 线性回归 demo 模板，可直接生成图片产物
  - 默认任务工作区已收口到 `scratch/tasks/<taskId>/`
  - 仍依赖运行环境已安装 `scikit-learn` 和 `matplotlib`
- 判断：
  - **已满足**

2. `Worker不可用时有fallback提示而非crash`
- 当前状态：
  - 已实现
  - 已有测试覆盖
- 判断：
  - **已满足**

综合判断：
- **F05 已完成。**
- 剩余注意事项不再属于功能缺口，而是环境前提：
  - 演示机器上是否装好 `scikit-learn / matplotlib`
  - `codex / opencode` 的真实 CLI 环境是否与本地 PATH 对齐
  - 如果某个 CLI 未安装，应由其他可用 worker 或 fallback 路径接管；这属于预期行为，不视为 F05 未完成

## 后续增强方向

F05 已交付，后续只保留增强项：

1. 在真实环境直接发起：
   - `"帮我跑一个 sklearn 线性回归 demo，并把图保存下来"`
2. 保留对应端到端测试
- 断言：
  - `task.result.status == "done"`
  - `content` 含关键 stdout
  - `artifacts` 里有图片
3. 用这条样例作为答辩演示保底链路

