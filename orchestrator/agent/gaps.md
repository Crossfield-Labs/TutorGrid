# 迁移缺口与框架职责

这份文档用于记录 `orchestrator/` 相对旧项目仍未完全对齐的内容，以及这些问题应该优先落在哪一层。

阅读建议：
1. 先看“当前剩余缺口”
2. 再看“框架职责划分”
3. 最后按“下一步建议顺序”继续推进

## 当前剩余缺口

### P0：行为已迁入但还需要继续校准

1. 委派链路虽然已经补回 `select_worker / select_session_mode / select_worker_profile / fallback reroute`，但还需要做真实联调。
   重点文件：
   - `orchestrator/tools/delegate.py`
   - `orchestrator/workers/selection.py`
   - `orchestrator/workers/*.py`
   风险：
   - 真实 CLI/SDK 环境下，失败重路由、session 续接、artifact 汇总是否和旧版一致，还没做系统回归。

2. `planning -> tools -> planning` 的多轮循环已经恢复，但 planner 仍然可能重复调用相同工具。
   重点文件：
   - `orchestrator/runtime/nodes/planning.py`
   - `orchestrator/runtime/routes/post_tools.py`
   - `orchestrator/llm/prompts.py`
   当前症状：
   - `dev.run_runtime` 里可能出现多次重复 `list_files`
   目标：
   - 减少重复工具调用
   - 更接近旧版 `_should_attempt_forced_finish()` 的成熟收口体验

3. human-in-the-loop 的协议层已补齐，但运行时恢复仍需要继续打磨。
   重点文件：
   - `orchestrator/server/app.py`
   - `orchestrator/runtime/nodes/await_user.py`
   - `orchestrator/runtime/nodes/planning.py`
   当前关注点：
   - `reply / redirect / comment / instruction / explain / interrupt` 在真实多轮任务中的恢复语义
   - follow-up 被消费后的 planner 上下文是否足够稳定

### P1：主能力已在，但还没做完整端到端验证

4. runner 层需要按旧项目使用方式完整联调。
   重点文件：
   - `orchestrator/runners/router.py`
   - `orchestrator/runners/shell_runner.py`
   - `orchestrator/runners/codex_runner.py`
   - `orchestrator/runners/claude_runner.py`
   - `orchestrator/runners/opencode_runner.py`
   - `orchestrator/runners/subagent_runner.py`
   需要验证：
   - `shell`
   - `codex_cli`
   - `claude_cli`
   - `pc_subagent`
   - `/ws/pc-agent` 兼容路径

5. WebSocket 协议虽然已经双命名空间兼容，但仍需要专门的协议回归。
   重点文件：
   - `orchestrator/server/app.py`
   - `orchestrator/server/protocol.py`
   需要验证：
   - `start / input / snapshot / interrupt / cancel`
   - `summary / phase / worker / snapshot / subnode.*`
   - 等待输入时的 explain / reply / redirect 行为

6. 测试覆盖不足。
   当前主要验证方式仍是：
   - `python -m compileall orchestrator`
   - `python -m orchestrator.dev.run_runtime ...`
   还需要补：
   - runtime 节点测试
   - delegate 工具测试
   - server 协议测试
   - follow-up / interrupt 集成测试

### P2：不是缺功能，但可以继续增强

7. prompt 约束虽然已经很接近旧版，但还可以继续针对“避免重复工具调用”“何时继续探索”“何时收口”做更强约束。

8. 当前有些信息仍然是 runtime 内部约定，不是显式 schema。
   例如：
   - `session.context["planner_messages"]`
   - `session.context["tool_events"]`
   - `session.context["_active_worker_control"]`
   后续可以继续把这些弱结构变成更明确的运行时状态或 typed model。

## 哪些应该交给 LangGraph

LangGraph 在这个项目里不该只是“跑一个 graph 壳”。

应该主要承担这些职责：

1. 运行时状态机
   - `planning`
   - `tools`
   - `delegating`
   - `awaiting_user`
   - `verifying`
   - `completed / failed`

2. 多轮循环控制
   - 什么时候继续 planning
   - 什么时候从 tools 回 planning
   - 什么时候进入 finalize
   - 什么时候等待用户输入

3. human-in-the-loop 恢复点
   - 等待输入
   - 恢复执行
   - interrupt 后跳转
   - follow-up 在安全点消费

4. checkpoint / 可恢复执行
   当前还没充分用上。
   后续应该考虑：
   - graph state checkpoint
   - session resume
   - replay / debug

5. 更清晰的状态投影
   - phase
   - stop_reason
   - active_worker
   - worker_sessions
   - tool_events
   - substeps

一句话：
LangGraph 负责“流程怎么跑、状态怎么转、什么时候停、什么时候恢复”。

## 哪些应该交给 LangChain

LangChain 在这里不该替代 runtime，而是做组件层。

应该主要承担这些职责：

1. prompt / message 抽象
   - planner prompt
   - message 序列化 / 反序列化
   - follow-up 注入后的消息组织

2. tool 抽象
   - `StructuredTool`
   - tool schema
   - tool metadata
   - tool definition 导出

3. model 交互标准化
   - planner 调用接口
   - tool-calling 消息格式
   - structured output 扩展点

4. 后续可能的增强能力
   - retriever / RAG
   - document loading
   - output parser
   - 更强的 structured output

一句话：
LangChain 负责“节点里怎么和模型、消息、工具交互”。

## 不该怎么做

1. 不要把 LangGraph 删掉然后退回手写 while-loop。
   原因：
   - 现在新的状态拆分已经成型
   - 回退会丢掉可维护性和可测试性

2. 不要把 LangChain 当成整个系统框架。
   原因：
   - 这个项目的核心问题是 orchestration，不是单条 chain

3. 不要为了“像旧版”而把所有逻辑重新塞回单文件 runtime。
   应该追求：
   - 行为尽量等价旧版
   - 结构保留新版分层

## 下一步建议顺序

1. 先做 runner + websocket 联调
   - 目标是验证新系统已经能按旧协议工作

2. 再压 delegate 链路
   - 验证 worker 选择、fallback、resume、profile

3. 然后处理 planner 的重复工具调用
   - 通过 prompt 约束和 loop 条件一起收敛

4. 最后补测试
   - 把当前已经能跑的路径固化成回归

## 文档维护要求

当以下内容变化时，必须同步更新本文件：

- 迁移缺口被补齐或新增
- LangGraph 职责边界调整
- LangChain 职责边界调整
- 下一步建议顺序改变
- 某项风险从“待处理”变成“已验证”

更新时不要只改状态结论，至少要写清楚：
- 改的是哪一层
- 对齐了旧版什么行为
- 还剩什么没有完成
