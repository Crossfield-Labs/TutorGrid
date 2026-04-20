# 下一阶段路线图

这份文档用于说明当前重构完成后的下一阶段重点工作，以及为什么优先级要调整为 **桌面 GUI 优先**。

## 当前判断

当前内核已经具备：
- WebSocket 协议入口
- session 状态管理
- LangGraph 运行时
- LangChain tool / message / planner 组件层
- codex / claude / opencode 的 worker 适配

当前真正缺的不是“还能不能跑”，而是：
- 可恢复的会话持久化
- 可观察的错误与 trace
- 更稳定的上下文压缩
- 更好的人机交互界面

## 为什么桌面 GUI 现在更重要

如果项目目标不仅是“能跑”，而是“能展示、能协作、能长期使用”，那桌面 GUI 的优先级高于 TUI。

原因：
1. GUI 更容易承载会话列表、时间线、状态侧栏、artifact 预览、错误详情。
2. GUI 更适合展示长任务、多 worker、异步恢复和历史会话。
3. GUI 更适合后续演示、协作和产品化。
4. 当前协议已经是 WebSocket 事件流，天然适合先接一个桌面端渲染层。

这不代表 TUI 不重要，而是：
- GUI 作为产品主入口优先
- TUI 作为开发/运维入口后补

## 前端技术方向

推荐：
- 前端语言：TypeScript
- 前端形态：桌面应用 GUI
- 桌面壳：Electron
- 通信方式：优先复用现有 WebSocket 协议

建议的前端结构：
- `frontend/`
  - `app/` 或 `src/`
  - `features/sessions/`
  - `features/timeline/`
  - `features/input/`
  - `features/state-panel/`
  - `lib/ws-client/`
  - `lib/protocol/`

第一版 GUI 至少应该有：
1. 会话列表
2. 主时间线
3. phase / worker / snapshot 侧栏
4. 输入框
5. explain / interrupt / snapshot 操作
6. 错误详情面板

## 先做 GUI，不代表可以跳过底层

GUI 优先的前提是补一层稳定基础设施，否则前端会反复返工。

前置项必须先做：
1. session 持久化
2. error 持久化
3. snapshot / trace 查询
4. 历史消息恢复
5. 基本上下文压缩

所以当前推荐顺序是：
1. 设计持久化
2. 补服务端查询与订阅协议
3. 做 Electron + TypeScript GUI 第一版
4. 再补 TUI

## LangGraph 在下一阶段的作用

LangGraph 不负责前端界面，但仍然是整个系统的运行时骨架。

它应该承担：
1. session 状态机
2. 多轮循环控制
3. interrupt / await_user / resume
4. checkpoint / 恢复入口
5. 可投影到前端的 phase / stop_reason / active_worker / substeps

在桌面 GUI 时代，LangGraph 的价值更明显：
- GUI 看到的时间线和状态变化，应该来自 LangGraph state 的稳定投影
- 历史恢复和“继续任务”，也应该建立在 graph checkpoint 或等价的持久状态上

一句话：
LangGraph 负责“任务如何持续运行、暂停、恢复、收口”。

## LangChain 在下一阶段的作用

LangChain 仍然不应该变成整个系统框架，它主要负责组件层。

它应该承担：
1. planner prompt / message 抽象
2. tool schema 和 tool metadata
3. model 调用标准化
4. structured output
5. 后续上下文压缩链、摘要链、RAG 链

在桌面 GUI 时代，LangChain 最值得继续扩展的方向是：
1. 压缩链
2. 摘要链
3. 错误解释链
4. 历史会话恢复时的上下文重建链

一句话：
LangChain 负责“节点里如何和模型、工具、消息、压缩策略交互”。

## 不该怎么做

1. 不要因为做 GUI 就把前端逻辑塞进 runtime。
2. 不要因为有 LangGraph 就让前端直接依赖 graph 内部实现。
3. 不要把 GUI、TUI、持久化各自做一套协议。
4. 不要把上下文压缩做成前端层行为，它应该属于后端运行时能力。

## 下一阶段的明确执行顺序

1. 设计 session / message / error / snapshot / trace 的持久化模型
2. 补 WebSocket 协议的历史查询、会话列表、trace 拉取
3. 做 TypeScript GUI 第一版
4. 补上下文压缩与恢复
5. 再做 TUI
6. 最后补完整的协议集成测试和前端契约测试

