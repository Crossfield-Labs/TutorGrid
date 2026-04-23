# Harness 说明

这份文档定义仓库内最小可用的 harness 结构。当前 `harness/` 已经同时承担两层职责：
- 模块导航与协作文档
- 可重复执行的任务框架

## 目标

harness 当前负责四件事：
- 任务定义
- 标准执行入口
- 标准结果产物
- 基础自动评测

## 当前目录

```text
harness/
├── __init__.py
├── models.py
├── evaluator.py
├── runner.py
├── docs/
│   ├── README.md
│   ├── current-focus.md
│   ├── gaps.md
│   ├── runtime.md
│   ├── server.md
│   ├── sessions.md
│   ├── tools.md
│   ├── workers.md
│   ├── frontend.md
│   └── testing.md
└── tasks/
    └── ws_contract_smoke.json
```

## 任务格式

当前任务文件使用 JSON。

示例字段：
- `taskId`
- `nodeId`
- `runner`
- `workspace`
- `task`
- `goal`
- `wsUrl`
- `timeoutSeconds`
- `querySnapshot`
- `queryHistory`
- `queryTrace`
- `queryErrors`
- `queryArtifacts`
- `historyLimit`
- `traceLimit`
- `errorsLimit`
- `artifactsLimit`
- `expectation`

`expectation` 当前支持：
- `requiredEvents`
- `terminalEvent`
- `terminalStatus`
- `requireFrameMetadata`
- `requireMessageStream`
- `minHistoryItems`
- `minTraceItems`
- `minErrorItems`
- `minArtifactItems`
- `requiredSnapshotFields`
- `requiredHistoryKinds`
- `requiredArtifactEvents`

## 执行入口

```powershell
python -m harness.runner --task-file harness/tasks/ws_contract_smoke.json
python -m harness.runner --task-dir harness/tasks
```

## 文档入口

如果是 agent 或开发者接手代码，优先看：
- `harness/docs/README.md`
- `harness/docs/current-focus.md`
- `harness/docs/gaps.md`
- 对应模块文档

## 结果产物

默认输出目录：

```text
scratch/harness-runs/<task-id>-<suffix>/
```

每次执行当前至少写出：
- `result.json`
- `evaluation.json`
- 批量模式下额外写出 `summary.json`

## 评测规则

当前 evaluator 只做协议层和基础行为检查：
- 需要的事件是否出现
- 终止事件是否符合预期
- snapshot 的终止状态是否符合预期
- history 数量是否达到最低要求
- trace / errors / artifacts 数量是否达到最低要求
- snapshot 必填字段是否齐全
- history kind 是否满足预期
- session 广播事件是否都带 `seq / timestamp`
- 如果要求消息流，`started/delta/completed` 是否齐全

## 与测试的关系

- `tests/test_websocket_e2e.py` 更偏 server 协议回归
- `tests/test_harness_runner.py` 更偏 harness 执行与产物格式回归

## 下一步可以继续补的方向

- 支持更丰富的 scorer
- 支持 artifact / tile / learning push 专项断言
- 支持把结果聚合成统一报告
