# Harness 模块

主要代码：
- `harness/models.py`
- `harness/runner.py`
- `harness/evaluator.py`
- `harness/tasks/`

职责：
- 定义可重复执行的任务输入格式
- 通过统一 WebSocket 入口驱动 orchestrator
- 把运行结果落成标准产物
- 对协议层和基础行为做最小自动评测

当前约定：
- 任务文件当前使用 JSON
- 统一入口：`python -m harness.runner --task-file <task-file>`
- 批量入口：`python -m harness.runner --task-dir harness/tasks`
- 产物目录默认落在 `scratch/harness-runs/`
- 每次执行至少产出：
  - `result.json`
  - `evaluation.json`
  - 批量执行时额外产出 `summary.json`

结果文件语义：
- `result.json`：保存任务输入、session_id、事件流、snapshot、history、trace、errors、artifacts
- `evaluation.json`：保存评测结论和逐项检查结果
- `summary.json`：保存批量任务的聚合结果

适用场景：
- 协议契约回归
- 端到端 smoke 验证
- 为前端、评测脚本、后续 benchmark 提供稳定输入输出
- 批量任务回归与汇总报告

修改时注意：
- 不要让 harness 直接依赖 runtime 私有结构
- 优先通过 `orchestrator.session.*` 协议驱动系统
- 新任务格式、新产物字段、新评测规则变化时同步更新本文件和 `docs/harness.md`
