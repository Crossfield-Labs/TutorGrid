# 迁移缺口与框架职责

这份文档用于记录当前新根目录实现相对旧项目仍未完全对齐的内容，以及这些问题应该优先落在哪一层。

阅读建议：
1. 先看“当前剩余缺口”
2. 再看“框架职责划分”
3. 最后按“下一步建议顺序”继续推进

## 当前剩余缺口

现在代码层面的主缺口已经补齐，剩下的是环境相关联调和端到端验证。

### P0：环境相关联调仍需要继续做

1. 委派链路的策略已经补齐，并有最小回归测试，但仍需要做真实 CLI/SDK 联调。
   重点文件：
   - `tools/delegate.py`
   - `workers/selection.py`
   - `workers/*.py`
   当前状态：
   - 已补齐 `select_worker / select_session_mode / select_worker_profile / fallback reroute`
   - 已补最小 `delegate` 回归测试
   风险：
   - 真实 CLI/SDK 环境下，失败重路由、session 续接、artifact 汇总是否和旧版一致，还需要系统联调。

2. `planning -> tools -> planning` 的多轮循环已经恢复，并补了重复工具调用抑制，但还需要继续观察真实模型行为。
   重点文件：
   - `runtime/nodes/planning.py`
   - `runtime/routes/post_tools.py`
   - `llm/prompts.py`
   当前状态：
   - 已补显式去重逻辑
   - 已补规划节点回归测试
   目标：
   - 继续减少模型层面的重复探索
   - 在真实任务里验证收口体验

3. human-in-the-loop 的协议层和输入分流已经补齐，并有最小回归测试，但仍需要做真实多轮交互联调。
   重点文件：
   - `server/app.py`
   - `runtime/nodes/await_user.py`
   - `runtime/nodes/planning.py`
   当前状态：
   - 已补输入分类 helper
   - 已补 `reply / redirect / comment / instruction / explain / interrupt` 的最小回归
   当前关注点：
   - 真实多轮任务里的恢复语义
   - follow-up 被消费后的 planner 上下文稳定性

### P1：主能力已在，但还没做完整端到端验证

4. runner 层需要按旧项目使用方式完整联调。
   重点文件：
   - `runners/router.py`
   - `runners/shell_runner.py`
   - `runners/codex_runner.py`
   - `runners/claude_runner.py`
   - `runners/opencode_runner.py`
   - `runners/subagent_runner.py`
   需要验证：
   - `shell`
   - `codex_cli`
   - `claude_cli`
   - `pc_subagent`
   - `/ws/pc-agent` 兼容路径

5. WebSocket 协议虽然已经双命名空间兼容，但仍需要专门的协议回归。
   重点文件：
   - `server/app.py`
   - `server/protocol.py`
   当前状态：
   - 已补旧版中的 session trace、workspace 准备、非法 JSON/非法 frame 失败事件
   - 已补更完整的 interrupt/cancel/snapshot/input 语义
   - 已补更接近旧版的 payload 字段
   需要验证：
   - `start / input / snapshot / interrupt / cancel`
   - `summary / phase / worker / snapshot / subnode.*`
   - 等待输入时的 explain / reply / redirect 行为

6. 测试已经从“只有 compileall 和手工直跑”提升到了最小回归级别，但仍缺真正的端到端协议测试。
   当前已有：
   - `python -m compileall orchestrator`
   - `python -m dev.run_runtime ...`
   - runtime 节点测试
   - delegate 工具测试
   - server 输入分类测试
   还需要补：
   - websocket 协议集成测试
   - runner 端到端测试
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

2. 再做真实 worker 环境压测
   - 验证 selection、fallback、resume、profile 在 CLI/SDK 下的行为

3. 最后补 websocket 级回归
   - 把协议路径固化成真正的集成测试

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

