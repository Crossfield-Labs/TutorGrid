# 前端方向说明

这份文档用于说明当前前端相关工作的边界，避免后端和前端各自演化出不兼容的模型。

## 当前判断

当前下一阶段优先级已经调整为：
- GUI 优先
- TypeScript 前端
- Chat 走 `SSE`，知识库 / 配置 / 画像走 `REST`
- TUI 后补
- 当前真实前端代码位于 `TutorGridFront/`
- 当前技术栈：`Electron + Vite + Vue 3 + TypeScript + Vuetify + Pinia`
- 当前路线：桌面应用优先

详细前后端协作与协议边界，优先参考：
- `../../docs/BackEndA/orchestrator-v5-protocol.md`
- `../../docs/harness.md`

## 前端实现规范（必须遵守）

前端组件库统一使用 `Vuetify 3`。

约束：
- 页面结构、输入控件、列表、按钮、表单、标签等，优先使用 `vuetify` 组件
- 图标优先复用当前项目已接入的 `@mdi/font` / `@iconify/vue`
- 主题统一通过 Vuetify theme 管理，不再额外并行维护第二套组件体系
- 状态管理优先复用 `Pinia`
- 仅在 Vuetify 无法覆盖的局部场景下，才允许小范围补充自定义样式

## 前端不应该直接依赖什么

前端不应该直接依赖：
- `backend/runtime/` 内部 graph 实现
- `backend/workers/` 内部返回细节
- `session.context` 里的弱结构字段

前端应该依赖：
- `backend/server/chat_api.py` 的 Chat SSE 事件格式
- `backend/server/http_app.py` 的 REST API
- 当前前端协议封装：
  - `TutorGridFront/src/lib/chat-sse.ts`
  - `TutorGridFront/src/stores/knowledgeStore.ts`

## GUI 第一版建议页面

1. 会话列表
2. 主时间线
3. 状态侧栏
4. 输入区
5. 错误详情
6. artifact 预览入口

当前已落地的第一版：
1. 会话列表骨架
2. 历史时间线拉取与渲染
3. 状态侧栏与 snapshot 详情
4. Chat SSE 连接壳
5. 统一输入模型：new / reply / redirect / instruction / explain / interrupt
6. Electron 桌面壳骨架
7. Vuetify 组件化页面骨架与 Pinia 状态接入

当前还没落地：
1. artifact 预览
2. 更细的 trace/错误筛选能力
3. 打包态下的内置后端联调验证

设置页约束：
- 继续统一使用 Vuetify 组件实现
- 布局优先使用 `VCard / VDivider / VForm / VSelect / VSwitch / VAlert / VProgressLinear`
- 保存、加载、同步状态时，优先使用 Vuetify 标准反馈组件，不要手搓进度条和状态条
- 运行时设置现在至少覆盖：连接、模型/API、记忆召回、自动整理策略
- 记忆区需要提供显式的“立即整理记忆”入口
- Inspector 需要支持概览、trace、errors、artifacts 四类真实数据页签

## 前端最需要后端先补的接口

1. 历史消息恢复
2. artifact 详情
3. 归档/删除/改名持久化

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
- Vuetify 主题和组件使用策略变化
- Electron 自动拉起本地后端的方式变化


