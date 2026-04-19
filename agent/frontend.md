# 前端方向说明

这份文档用于说明当前前端相关工作的边界，避免后端和前端各自演化出不兼容的模型。

## 当前判断

当前下一阶段优先级已经调整为：
- GUI 优先
- TypeScript 前端
- WebSocket 协议复用
- TUI 后补
- 当前第一版前端代码骨架位于 `frontend/`
- 当前技术栈：`Electron + Vite + React + TypeScript`
- 当前路线：桌面应用优先

详细产品路线看：`../docs/roadmap.md`

## 前端不应该直接依赖什么

前端不应该直接依赖：
- `runtime/` 内部 graph 实现
- `workers/` 内部返回细节
- `session.context` 里的弱结构字段

前端应该依赖：
- `server/protocol.py` 的稳定事件模型
- `sessions/state.py` 投影出来的 snapshot 字段
- 后续会补的历史查询和 trace 拉取接口
- 当前前端协议封装：
  - `frontend/src/lib/protocol.ts`
  - `frontend/src/lib/ws-client.ts`

## GUI 第一版建议页面

1. 会话列表
2. 主时间线
3. 状态侧栏
4. 输入区
5. 错误详情
6. artifact 预览入口

当前已落地的第一版：
1. 会话列表骨架
2. 时间线骨架
3. 状态侧栏骨架
4. WebSocket 连接壳
5. 最小联调动作：start / input / snapshot / explain
6. Electron 桌面壳骨架

当前还没落地：
1. 输入区
2. explain / interrupt / snapshot 操作
3. 历史列表查询
4. 错误详情
5. artifact 预览

## 前端最需要后端先补的接口

1. 会话列表
2. 历史会话详情
3. snapshot 拉取
4. trace 拉取
5. 错误详情
6. 历史消息恢复

## LangGraph 在前端阶段的作用

LangGraph 不在前端运行，但前端会消费它投影出来的状态变化。

对前端最关键的是这些字段：
- `phase`
- `status`
- `stop_reason`
- `active_worker`
- `active_worker_profile`
- `awaiting_input`
- `pending_user_prompt`
- `recentHookEvents`
- `artifacts`

## LangChain 在前端阶段的作用

LangChain 也不在前端运行，但会影响前端展示内容。

例如：
- planner summary
- 工具调用摘要
- 上下文压缩摘要
- 错误解释文本

所以前端需要的是稳定的输出字段，不是 LangChain 内部对象。

## 文档维护要求

如果以下内容变化，必须更新本文件：
- GUI / TUI 优先级变化
- 前端通信协议变化
- 前端依赖字段变化
- TypeScript 前端目录规划变化
