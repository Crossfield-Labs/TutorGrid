# F07 · 文档内 Chat 气泡 + 浮窗对话整合

> 前端A · 2026-05-01 工作记录
> 任务书引用：[智格生境_V5_项目任务书.md](../智格生境_V5_项目任务书.md) §F07 / §F10 / §F11

## 本次范围

落地任务书 **F07（文档内 Chat 气泡）+ F10（统一消息 Store）+ F11（Chat 独立面板）** 三项的核心骨架，前端 A 一条线全做完。

**核心交付：**
- 文档区可以通过 slash 命令 / 选中气泡菜单触发 AI 对话，回答会以"气泡节点"形式嵌入文档
- 右下角浮窗（ChatAssistant）和文档气泡共享同一份会话历史（同一个 sessionId）
- 一个 Hyper 文档 = 一个 sessionId，持久化到 `tile.metadata.sessionId`，跨打开恢复
- 真实接 F01 后端 SSE（`POST /api/chat/stream`），不再 Mock

---

## 改动清单

### 新增文件（6 个）

| 文件 | 作用 |
|------|------|
| [src/lib/chat-sse.ts](../../TutorGridFront/src/lib/chat-sse.ts) | SSE 客户端封装。fetch + ReadableStream，按 `start / tool_call / tool_result / delta / done / error` 6 类事件分发到回调。 |
| [src/lib/markdown.ts](../../TutorGridFront/src/lib/markdown.ts) | `marked` + `DOMPurify` 渲染。流式重渲染零状态、无闪烁。`postProcessLinks` 给外链加 `target="_blank"`，配合 Electron `setWindowOpenHandler` 用系统浏览器开。 |
| [src/stores/messageStore.ts](../../TutorGridFront/src/stores/messageStore.ts) | F10 统一消息 Store。按 `sessionId` 分组的 `UnifiedMessage[]`，提供 `addUserMessage / startAiMessage / appendDelta / finishMessage / addCitations / addToolUsed` 等动作。 |
| [src/stores/chatSessionStore.ts](../../TutorGridFront/src/stores/chatSessionStore.ts) | 当前会话状态。`currentSessionId / currentDocId / courseId`。HyperdocPage 进入时写入，BoardPage 用 `GLOBAL_SESSION_ID` 兜底。 |
| [src/views/document/extensions/ai-bubble-node.ts](../../TutorGridFront/src/views/document/extensions/ai-bubble-node.ts) | TipTap Block-level Atom 节点。Attrs：`{ sessionId, userMessageId, aiMessageId, command }`。Commands：`insertAiBubble / removeAiBubbleById`。 |
| [src/views/document/extensions/ai-views/AiBubble.vue](../../TutorGridFront/src/views/document/extensions/ai-views/AiBubble.vue) | NodeView 组件。从 `messageStore` 拉对应 message 实时渲染，左 AI 头像 + 右用户头像 + 工具调用 chip + markdown 内容 + 流式打字提示。 |

### 修改文件（5 个）

| 文件 | 改动 |
|------|------|
| [DocumentEditor.vue](../../TutorGridFront/src/views/document/components/DocumentEditor.vue) | 注册 `AiBubbleNode` 扩展；新增 `sessionId` prop；`runAiCommand` 实现 SSE 完整链路；`onSlashSelect` 重写为格式块分发器；`onAi`（气泡菜单）触发 AI；删除底部 footer 的 "AI 已断开（mock）" 干扰文案，改为静态 "AI 就绪"。 |
| [HyperdocPage.vue](../../TutorGridFront/src/views/document/HyperdocPage.vue) | onMounted 时读 `tile.metadata.sessionId` 或新建并持久化；通过 `chatSession.setSession()` 注入全局；onBeforeUnmount 复位 `GLOBAL_SESSION_ID`。 |
| [ChatAssistant.vue](../../TutorGridFront/src/components/ai/ChatAssistant.vue) | 替换为 messageStore 数据源 + SSE 发送链路；标题栏加 `+` 新建会话按钮（重生成 sessionId 并写回 tile.metadata）；副标题显示当前 session 来源（"全局会话" / "文档会话 · xxxx"）；`<perfect-scrollbar>` 替换为原生 `overflow-y: auto`。 |
| [EditorBubbleMenu.vue](../../TutorGridFront/src/views/document/components/EditorBubbleMenu.vue) | 删除 `generate-quiz` / `generate-flashcards` 两个已废弃 AI 命令（迁移至 F14 + 右侧磁贴）。 |
| [slash-command-items.ts](../../TutorGridFront/src/views/document/extensions/slash-command-items.ts) | 完全重写：从"AI 命令清单"重设计为"格式块插入清单"——H1/H2/H3、有序/无序列表、代码块、引用、分隔线，加一个"向 AI 提问"通用入口。 |

### `package.json` 新增依赖

```json
"marked": "^xx",         // markdown 解析
"dompurify": "^xx",      // XSS 过滤
"@types/dompurify": ...  // 类型声明
```

---

## 关键设计决策

### 1. Slash 菜单 ≠ 气泡菜单（UX 拆分）

**之前**：两边都堆 AI 命令，混乱。

**现在**：
- **Slash `/`**（无选区） = 插入格式块（参考 Notion）+ 1 个"向 AI 提问"
- **选中气泡菜单**（有选区） = AI 操作（讲解/总结/改写/续写/问知识库/发送 chat）

直觉上：slash = "我要在这里插入什么"，气泡 = "对选中的文字做什么"。

### 2. Session 共享模型

```
HyperdocPage 进入文档
   ├─ 读 tile.metadata.sessionId（没有就新建）
   ├─ chatSession.setSession(sessionId, docId)
   └─ 把 sessionId 通过 prop 传给 DocumentEditor

DocumentEditor.runAiCommand
   ├─ messageStore.addUserMessage(sessionId, ...)
   ├─ messageStore.startAiMessage(sessionId, ...)
   ├─ editor.commands.insertAiBubble({ sessionId, userMessageId, aiMessageId })
   └─ streamChat → 写回 messageStore（同一个 sessionId）

ChatAssistant（浮窗，全局）
   ├─ chatSession.currentSessionId（响应式）
   └─ messageStore.getSessionMessages(sessionId) → 同一份数据
```

文档气泡和浮窗看到的是同一个 timeline，零额外同步代码。

### 3. AiBubbleNode 用 atom

```ts
atom: true,    // 节点内容不可编辑（避免用户改文档时打破气泡结构）
```

气泡内的文字流来自 `messageStore`（响应式），删除气泡只是从 doc 移除节点（消息记录仍保留在 store，浮窗里还能看见历史）。

### 4. 流式渲染

每次 SSE delta：
```ts
messageStore.appendDelta(sessionId, aiMessageId, delta)
```

由 Pinia 响应式触发 AiBubble.vue 和 ChatAssistant.vue 同时重渲染。`marked.parse()` 是纯函数，每次 delta 重新渲染整段 markdown 零状态、零闪烁，代码块、列表、引用都流畅。

### 5. 选第三方库的踩坑记录

| 选型 | 决定 | 理由 |
|------|------|------|
| `md-editor-v3` MdPreview | ❌ 弃用 | 包大（500KB）、流式频繁 mount/unmount 闪烁、HMR/scoped/dark 多 issue |
| `marked` + `DOMPurify` | ✅ 采用 | 50+30 KB、纯函数、流式友好、API 极简 |
| `vue3-perfect-scrollbar` | ❌ 弃用 | 旧项目复用时漏掉了全局注册，组件渲染但滚动行为缺失，"看起来正常但滚不动"是隐蔽 bug。换原生 `overflow-y: auto` 直接干净。 |
| `grid-layout-plus`（F06 已用） | ✅ 保留 | 磁贴推挤行为在这里不冲突。 |

---

## 顺带清理（旧 ai-block 体系）

为给 F07 让路，把 V4 时期的多类型 AI 卡片体系整套清掉：

**删除：**
- `extensions/ai-block.ts` / `ai-block-types.ts`（旧 TipTap 扩展和类型）
- `extensions/mock-ai-data.ts`（演示模式 Mock 数据）
- `extensions/markdown-parsers.ts`（Quiz / Flashcard 解析）
- `extensions/ai-views/Text.vue / Quiz.vue / Flashcard.vue / Citation.vue / Agent.vue / AiBlockDispatcher.vue / Placeholder.vue / UnknownBlock.vue`（8 个视图）
- `components/ChatFAB.vue`（旧 Drawer 抽屉，被 Toolbox 替代）
- `orchestratorStore.forceMock` / `setForceMock` 字段 + HyperdocPage 顶部 "A/B 模式" 切换按钮 + "重置会话" 按钮

**DocumentEditor.vue 体积**：1058 → 570 行（砍掉 488 行旧流水线代码）。

**功能回退：** 旧 AsidePanel 的 "工作区文件 / 知识库" 两个 Tab 暂时丢失，未来由前端 B 在 F08/F09 阶段做成 `WorkspaceFilesTile` / `KnowledgeTile` 重新加回（已在 F06 文档说明里登记）。

---

## 已知未做（留给后续）

| 项 | 归宿 |
|------|------|
| Citations 渲染成 CitationTile 磁贴 | F09（前端 B） |
| 编排任务（`/task` 命令）走 WebSocket → TaskTile | F12（前端 A + 后端 A 协作）|
| 测验/闪卡 AI 自动产出磁贴 | F14 |
| 浮窗里发的消息插入文档 | UX 决定后再说，目前只在浮窗显示 |
| `messageStore` 持久化（刷新不丢） | F11 后续优化或新增小 store |
| 暗色主题适配 AiBubble | 可视化优化，看时间 |

---

## 验收

- [x] 进入 Hyper 文档时自动建/复用 sessionId
- [x] 文档输入 `/` → 弹出格式块菜单（不再是 AI 命令）
- [x] 选中文字 → 浮气泡菜单 → AI 命令 → 文档当前位置插入气泡 + 流式回答
- [x] 右下角浮窗能看到同一份对话历史
- [x] 浮窗里发消息也能流式回答
- [x] 浮窗滚动正常，长对话不挤掉输入框
- [x] 浮窗 `+` 新建会话能开新 session
- [x] curl 直测 `/api/chat/stream` 通过

---

## 快速运行

```bash
# 后端（HTTP 服务，独立于编排 WebSocket）
cd pc_orchestrator_core
python -m uvicorn backend.http_main:app --host 127.0.0.1 --port 8000

# 前端
cd TutorGridFront
yarn install        # 装新依赖（marked / dompurify / @types/dompurify）
yarn electron:dev
```

确保 `config.json` 的 `planner.apiKey` 是有效的 DeepSeek key（或其它 OpenAI 兼容 key），不然会回退到 "当前无法调用LLM" fallback。

---

*前端 A · 波 · 2026-05-01*
