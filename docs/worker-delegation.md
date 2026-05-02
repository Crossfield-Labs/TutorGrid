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
  - 但“真实 sklearn demo + 真实图片产物”还没有形成稳定验收样例
- 判断：
  - **未完全验收**

2. `Worker不可用时有fallback提示而非crash`
- 当前状态：
  - 已实现
  - 已有测试覆盖
- 判断：
  - **已满足**

综合判断：
- **F05 现在可以算“开发完成度较高”，但还不能严格按任务书口径宣称完全交付。**
- 最后一段缺的是：
  - 真实 `sklearn` 线性回归样例
  - 明确产出图片文件并通过 `task.result` 返回

## 下一步最小补齐方案

如果要把 F05 从“基本可交付”推到“可验收交付”，建议只再补一条最小样例：

1. 增加一个固定的 Python Runner demo 输入
- 生成：
  - `stdout`
  - 一张本地 `png`

2. 增加对应端到端测试
- 断言：
  - `task.result.status == "done"`
  - `content` 含关键 stdout
  - `artifacts` 里有图片

3. 用这条样例作为答辩演示保底链路

