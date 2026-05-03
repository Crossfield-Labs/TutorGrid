# 迁移缺口与框架职责

这份文档用于记录当前新根目录实现相对旧项目仍未完全对齐的内容，以及这些问题应该优先落在哪一层。

阅读建议：
1. 先看“当前剩余缺口”
2. 再看“框架职责划分”
3. 最后按“下一步建议顺序”继续推进

## 当前剩余缺口

现在缺口已经不只是环境联调，还包括下一阶段产品化能力。

### P0：下一阶段基础设施

1. 缺少 session 持久化层。
   重点目录：
   - `backend/sessions/`
   - `backend/server/`
   - `backend/runtime/`
   需要补：
   - session 持久化
   - planner_messages 持久化
   - snapshots / traces 落库或稳定落盘
   - 历史会话恢复入口

2. 缺少错误持久化和结构化错误模型。
   重点目录：
   - `backend/runtime/`
   - `backend/workers/`
   - `backend/server/`
   需要补：
   - planner / tool / worker / transport error 分类
   - retryable 标记
   - 错误查询与展示所需字段

3. 缺少完整的上下文压缩与长期记忆治理能力。
   重点目录：
   - `backend/llm/`
   - `backend/runtime/`
   - `backend/memory/`
   - `backend/sessions/`
   需要补：
   - 长会话压缩策略
   - 历史摘要与恢复机制
   - 文件证据与聊天历史分层
   当前状态：
   - 已开始落 `SQLite` 记忆层与历史压缩
   - 已有本地记忆检索接口
   - 已把记忆召回接入 planner 前的上下文注入
   - 已补 `L1/L2/L3/L4` 记忆分层
   - 已补 knowledge ingest / RAG query / learning profile 基础链路
   - 还缺更强的整理策略：合并、降级、归档、过期

4. GUI 所需的历史查询和展示协议仍未完全补齐。
   重点目录：
   - `backend/server/`
   - `backend/sessions/`
   当前已补：
   - 会话列表
   - 历史 session 加载
   - snapshot 拉取
   - trace / errors / artifacts 查询
   仍需补：
   - 更细的 artifact 详情能力
   - GUI 所需的更多稳定字段

### P1：环境相关联调与后续增强

5. 委派链路的策略已经补齐，并有最小回归测试，但仍需要做真实 CLI/SDK 联调。
   重点文件：
   - `backend/tools/delegate.py`
   - `backend/workers/selection.py`
   - `backend/workers/*.py`
   当前状态：
   - 已补齐 `select_worker / select_session_mode / select_worker_profile / fallback reroute`
   - 已补最小 `delegate` 回归测试
   当前判断：
   - F05 已按任务书完成。
   - 这里记录的是环境联调和后续增强，不再视为 F05 功能缺口。

6. `planning -> tools -> planning` 的多轮循环已经恢复，并补了重复工具调用抑制，但还需要继续观察真实模型行为。
   重点文件：
   - `backend/runtime/nodes/planning.py`
   - `backend/runtime/routes/post_tools.py`
   - `backend/llm/prompts.py`
   当前状态：
   - 已补显式去重逻辑
   - 已补规划节点回归测试
   目标：
   - 继续减少模型层面的重复探索
   - 在真实任务里验证收口体验

7. human-in-the-loop 的协议层和输入分流已经补齐，并有最小回归测试，但仍需要做真实多轮交互联调。
   重点文件：
   - `backend/server/app.py`
   - `backend/runtime/nodes/await_user.py`
   - `backend/runtime/nodes/planning.py`
   当前状态：
   - 已补输入分类 helper
   - 已补 `reply / redirect / comment / instruction / explain / interrupt` 的最小回归
   - `tools_node -> await_user_node` 已开始切到 `interrupt()/Command(resume=...)`
   当前判断：
   - F04 已按任务书完成。
   - 这里记录的是稳定化关注点，不再视为 F04 功能缺口。

### P2：主能力已在，但还没做完整端到端验证

8.1. 知识库 / RAG / 学习画像已经具备最小可用链路，但还缺真实数据和真实部署环境下的系统联调。
   重点目录：
   - `backend/knowledge/`
   - `backend/rag/`
   - `backend/vector/`
   - `backend/learning_profile/`
   - `backend/observability/`
   当前状态：
   - 已支持课程创建、文件摄取、chunk 持久化、课程级重嵌入和重建索引
   - 已支持 `dense + lexical + rerank` 的 RAG 查询链路
   - 已补开发期评测、profile compare、grid tuning、workflow 汇总脚本
   - 已补 LangSmith best-effort tracing
   风险：
   - 真正课程资料上的解析成功率、OCR 耗时和 embedding 质量还未系统验收
   - `faiss/chroma/json` fallback 在不同机器上的表现仍需回归
   - 外部 rerank / embedding API 的失败退化路径还要继续做环境联调

8. runner 层需要按旧项目使用方式完整联调。
   重点文件：
   - `backend/runners/router.py`
   - `backend/runners/shell_runner.py`
   - `backend/runners/codex_runner.py`
   - `backend/runners/claude_runner.py`
   - `backend/runners/opencode_runner.py`
   - `backend/runners/subagent_runner.py`
   需要验证：
   - `shell`
   - `codex_cli`
   - `claude_cli`
   - `pc_subagent`
   - `/ws/pc-agent` 兼容路径
   当前新增进展：
   - `python_runner` 已补产物 diff、`worker_runs` 持久化和协议回传
   - `task.create -> python runner -> task.result` 已有回归测试
   说明：
   - 这部分记录的是更广义 runner 兼容路径，不改变 F05 已完成的判断。

9. WebSocket 协议虽然已经双命名空间兼容，但仍需要专门的协议回归。
   重点文件：
   - `backend/server/app.py`
   - `backend/server/protocol.py`
   当前状态：
   - 已补旧版中的 session trace、workspace 准备、非法 JSON/非法 frame 失败事件
   - 已补更完整的 interrupt/cancel/snapshot/input 语义
   - 已补更接近旧版的 payload 字段
   需要验证：
   - `start / input / snapshot / interrupt / cancel`
   - `summary / phase / worker / snapshot / subnode.*`
   - 等待输入时的 explain / reply / redirect 行为

10. 测试已经从“只有 compileall 和手工直跑”提升到了最小回归级别，但仍缺真正的端到端协议测试。
   当前已有：
   - `python -m compileall .`
   - `python -m backend.dev.run_runtime ...`
   - runtime 节点测试
   - delegate 工具测试
   - server 输入分类测试
   - protocol / runner router / session snapshot 测试
   - python runner 产物与 `worker_runs` 测试
   - `orchestrator.task.create -> python runner -> task.result` 协议测试
   还需要补：
   - 真实 worker CLI 端到端测试
   - LangGraph 原生 interrupt/resume 端到端测试
   - follow-up / interrupt 在真实模型上的系统联调

### P3：不是缺功能，但可以继续增强

11. prompt 约束虽然已经很接近旧版，但还可以继续针对“避免重复工具调用”“何时继续探索”“何时收口”做更强约束。

12. 当前有些信息仍然是 runtime 内部约定，不是显式 schema。
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
   当前仍未充分用上。
   后续应该考虑：
   - graph state checkpoint
   - session resume
   - replay / debug

6. 为 GUI 提供稳定状态投影
   - 时间线节点
   - 会话恢复点
   - 历史状态回放
   - 错误与压缩结果投影

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
   - 上下文压缩链
   - 错误解释链
   - 历史恢复时的摘要重建链

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

1. 先设计 session / error / snapshot / trace 的持久化模型
   - 目标是为 GUI 和恢复能力打底
   - 设计文档：`../docs/persistence.md`

2. 先完成 F04 的任务级编排协议适配
   - 目标是让前端改走 `orchestrator.task.*`
   - 设计文档：`../../docs/BackEndA/orchestrator-v5-protocol.md`

3. 再看是否还需要继续保留旧 session 调试协议的回归能力
   - 目标是区分“前端主契约”和“历史调试通道”

4. 然后做 TypeScript GUI 第一版
   - 目标是先把会话列表、时间线、状态侧栏跑起来

5. 再补上下文压缩和恢复
   - 目标是让长会话真正可用

6. 最后补 TUI 和端到端协议回归
   - 目标是统一产品入口和开发入口

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



