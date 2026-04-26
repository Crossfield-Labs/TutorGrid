# Hyper 文档页（笔记工作区）设计与交接文档

> 路由 `/hyperdoc/:id`，是 MetaAgent V4 的核心创新载体。本文档供新对话开箱即用。

---

## 一、定位与核心理念

### 1.1 在 MetaAgent V4 里的位置

MetaAgent V4 是「磁贴式 AI 学习工作区」，由三件套组成：

1. **磁贴工作区**（`/board`，已完成）—— Bento 风格的资料管理面板
2. **Hyper 文档工作区**（`/hyperdoc/:id`，**当前在做**）—— TipTap 编辑器 + AI 共做
3. **Chat 面板**（已降级为 ChatFAB 浮窗辅助）

后端是另一个项目 `pc_orchestrator_core`，本地跑（`ws://127.0.0.1:3210/ws/orchestrator`），前端只通过 WebSocket 接入。

### 1.2 核心命题：「你写它回」

不是 ChatGPT（你问它答），不是 Notion AI（你点它写），而是：

- 用户写笔记，AI **看着** 用户写
- 召唤它（选中文字 / Slash 命令）→ AI 在 **文档原位** 产出
- 产出不是话，是 **可交互的卡片**（测验卡能做题、闪卡能翻面、Agent 卡能跑任务）
- 重开文档，所有 AI 卡都还在、答题状态都还在
- 用户写的它能改，它写的用户能撤——**双向共同作者**

**这就是 Meta 感的核心。** 一句话能给评委讲清楚：「我们的 AI 不是被叫了才出现，它在你写错的瞬间就告诉你」。

### 1.3 双通道 AI（关键架构决策）

```
┌─ 主笔记区 (v-col=9) ──────────┐ ┌─ 辅助区 (v-col=3) ─┐
│ 用户写 + 选中召唤              │ │ Tab 切换：          │
│ AI 在文档里"长出"卡片          │ │ 工作区文件 / 节点详情 │
│ ↑ 聚焦、原位、深耕              │ │ ↑ 元信息、不抢焦   │
└────────────────────────────────┘ └─────────────────────┘
                              ┌─🤖 Chat (右下 FAB)─┐
                              │ 全局漫谈           │
                              │ 共享 sessionId     │
                              └────────────────────┘
```

**共享 sessionId**：每个 hyperdoc 绑一个 sessionId，存 `tile.metadata.sessionId`。BubbleMenu 命令、Slash 命令、ChatFAB 输入 **都走同一个会话** —— "用户在文档里选中问完，关 Chat → 1 小时后右下 Chat 问'上次那段你讲的再深入一下' → AI 知道指什么"。

---

## 二、设计决策史（重要：避免新对话走回头路）

| 决策点 | 早期想法 | 最终方案 | 原因 |
|------|---------|---------|------|
| 列宽分配 | 8/4 | **9/3** | 用户改的，更聚焦笔记 |
| 右栏交互 | 栈式上下文敏感 | **Vuetify v-tabs**（文件列表 / 节点详情）| 用户要 Vuetify3 规范 |
| Chat 位置 | 右栏 Tab 之一 | **右下 FAB 浮窗** | 不抢焦点，全局漫谈 |
| 编辑器底座 | 抄 vuetify-pro-tiptap 全套 | **复用项目已有的 [`RichEditorMenubar.vue`](../src/views/document/components/RichEditorMenubar.vue)** | 用户已写过，简单干净 |
| 图片插入 | OSS 上传 | **base64 内嵌** | 本地 app 无后端 OSS |
| 文档存储 | ProseMirror JSON | **HTML 字符串存到 .md** | 简单，TipTap 原生支持 |
| 文档高度 | 自然延伸 | **锁视口高度 + 内部滚** | 防止内容过长把右栏顶飞 |
| 后端职责 | 前端管 doc/AI | **前端只 WebSocket 消费**，不读 runtime 内部 | 后端约束 |
| 主动触发 (`tiptap.observe`) | 不确定 | **后端会加** | P1 高分项 |
| PDF 导出 | MD 导出 | **Electron printToPDF** | 一行代码搞定 |

---

## 三、当前完成状态

### 3.1 已落地的文件清单

```
src/views/document/
  ├── HyperdocPage.vue                 ← 主页：v-col=9/3、固定一屏高度
  └── components/
      ├── DocumentEditor.vue           ← TipTap 包装（StarterKit + Image + Highlight）
      ├── RichEditorMenubar.vue        ← 用户已有，OSS 上传已改 base64
      ├── EditorBubbleMenu.vue         ← 选中浮出，13 个 AI 按钮（mock）
      ├── AsidePanel.vue               ← v-tabs + v-list + vuedraggable
      └── ChatFAB.vue                  ← 右下浮按钮 + 抽屉 Chat（mock 回复）
```

### 3.2 已就位的能力

✅ **路由** `/hyperdoc/:id`（[`router/index.ts`](../src/router/index.ts)）  
✅ **TipTap 富文本** —— 标题/段落/加粗/斜体/删除线/突出/列表/引用/代码/HR/换行/清除/撤销重做  
✅ **图片插入** —— FileReader → base64 → `setImage`（离线工作）  
✅ **BubbleMenu** —— 选中文字浮出，4 格式按钮 + 3 主导命令(送Chat/改写/帮我做) + 5 学习命令(讲解/总结/续写/出题/闪卡) + 1 知识库  
✅ **右栏 Tab** —— 工作区文件 / 节点详情，文件可拖（vuedraggable + HTML5 dragstart 双挂）  
✅ **持久化** —— 内容 600ms debounce 写入 `hyperdocs/{uuid}.md`，标题改名同步到 [`workspaceStore`](../src/stores/workspaceStore.ts)  
✅ **保存状态指示** —— 编辑器底栏 chip "保存中/已保存/失败"  
✅ **字符计数** —— 编辑器底栏  
✅ **页面高度锁死** —— 锁视口高度 + 左右两栏 perfect-scrollbar 内部滚  
✅ **ChatFAB 占位** —— 浮按钮 + 抽屉 Chat（mock 600ms 回复"等接好后端再回"）

### 3.3 已就位但未联通

⚠️ BubbleMenu 13 个按钮 → emit 上去就 toast"待 Phase 2 接入"，**没真做事**  
⚠️ 拖文件出右栏 → 编辑器没接 drop 事件  
⚠️ 导出 PDF 按钮 → toast 占位  
⚠️ 右栏「节点详情」Tab → 永远显示空态（活跃 agent / selectedCard 一直 null）  
⚠️ Chat 输入 → 假回复

---

## 四、数据模型

### 4.1 Tile（已定型，[workspaceStore.ts](../src/stores/workspaceStore.ts)）

```ts
interface Tile {
  id: string;
  column: string;             // TODO/INPROGRESS/...
  order: number;
  title: string;
  description?: string;
  kind: 'note' | 'file' | 'hyperdoc';
  source?: FileSource | HyperdocSource;
  createdAt: number; updatedAt: number;
  // 待加：metadata: { sessionId?: string } —— 共享会话用
}
```

### 4.2 AI Block（待写，TipTap 自定义 Node）

```ts
{
  type: 'aiBlock',
  attrs: {
    id: 'ab_xxx',
    kind: 'text' | 'quiz' | 'flashcard' | 'agent' | 'placeholder' 
        | 'code' | 'citation' | 'mindmap' | 'deep-dive',
    sessionId: 'sess_yyy',
    createdBy: 'ai' | 'user-prompt',
    createdAt: number,
    data: {/* kind 专属 */},
    userState: {/* 用户答题/翻面状态 */},
  }
}
```

### 4.3 后端协议（关键，照搬 [Core 项目介绍.md](Core项目介绍.md)）

**WS 端点**：`ws://127.0.0.1:3210/ws/orchestrator`

**TipTap 命令双模式**：`orchestrator.tiptap.command`
- `execute=false` → preview 任务意图
- `execute=true` 无 sessionId → 开新会话（返回 sessionId）
- `execute=true` 带 sessionId → 注入 follow-up instruction

**内置命令**：`explain-selection / summarize-selection / rewrite-selection / continue-writing / generate-quiz / generate-flashcards / ask`

**会话事件**（必消费）：
```
session.message.started / .delta / .completed   ← 流式正文
session.phase / .summary / .snapshot            ← 状态变化
session.completed / .failed
```

**knowledge.rag.query** —— 接 citation block 用

---

## 五、未完成工作（执行计划）

### Phase 2 · AI Block 扩展骨架（下一步从这开始）

| Step | 任务 | 关键文件 |
|------|------|---------|
| 2.1 | 写 `extensions/ai-block.ts` —— 自定义 Node + kind 路由 NodeView | `src/views/document/extensions/ai-block.ts` |
| 2.2 | 写 5 个 P0 NodeView | `extensions/ai-views/{Placeholder,Text,Quiz,Flashcard,Agent}.vue` |
| 2.3 | 写 Slash command 扩展（`/explain` 触发） | `extensions/slash-command.ts` |
| 2.4 | BubbleMenu 命令派发到 ai-block 插入 | 改 `EditorBubbleMenu.vue` 现有 emit 链路 |

**P0 5 种 NodeView 优先级**：
- `Placeholder` 最简单（流式占位动画）—— 先做这个把流式管道跑通
- `Text` 紫边富文本（讲解/总结/续写）
- `Quiz` 单选/多选 + userState 持久化
- `Flashcard` 翻面 + userState
- **`Agent` ⭐ 最复杂、最值得做**（流式进度 + await_user 内嵌问答 + 产物列表 + 中断/撤回）

### Phase 3 · 接后端 WebSocket

| Step | 任务 |
|------|------|
| 3.1 | 写 `useOrchestratorStore` —— WS 单例 / req/event 派发 / sessionId 管理 / 事件订阅 |
| 3.2 | 接 `tiptap.command` 双阶段（preview 确认 → execute）|
| 3.3 | `session.message.delta` 流式 → Placeholder 逐字填字 |
| 3.4 | Agent block 接 `session.phase` / `awaiting_user` / artifacts |
| 3.5 | 右栏「节点详情」Tab 接收 card 点击 + agent 进度数据 |
| 3.6 | ChatFAB 接共享 sessionId（Chat 输入走 `session.input` follow-up）|
| 3.7 | 文件拖入编辑器 → 自动建 citation block（接 drop 事件）|

### Phase 4 · 加分项

| Step | 任务 | 备注 |
|------|------|------|
| 4.1 | P1 四种 block：`code` / `citation` / `mindmap` / `deep-dive` | code 用 iframe srcdoc 沙箱，mindmap 用 markmap.js |
| 4.2 | RAG 按钮 → `knowledge.rag.query` → citation block 流 | 引用展开 + 副"打开 PDF"按钮 |
| 4.3 | 主动触发 —— 监听用户输入 debounce 调 `tiptap.observe` | **答辩高分项**：「AI 在你写错时主动冒出来」 |
| 4.4 | PDF 导出 —— Electron `webContents.printToPDF` + 各 NodeView 写 `@media print` CSS | 隐藏右栏/工具栏 |

---

## 六、关键技术约束

| 项目 | 值 |
|------|-----|
| Vue | 3.2.47 |
| Vuetify | 3.3.6 |
| TipTap | `@tiptap/vue-3@2.0.2` `@tiptap/starter-kit@2.0.2` `@tiptap/extension-image@2.0.2` `@tiptap/extension-highlight@2.0.2` `@tiptap/pm@2.0.2` |
| 拖拽库 | `vuedraggable@4.1.0` + HTML5 dragstart 双挂 |
| 滚动 | `vue3-perfect-scrollbar@1.6.1` |
| Electron | 41.3.0 |
| 工作区根目录 | `D:\SoftInnovationCompetition\TestFolder` |
| 工作区结构 | 扁平：根目录直接放文件，`hyperdocs/{uuid}.md` 单独子目录，`tiles.json` 索引 |
| 后端 WS | `ws://127.0.0.1:3210/ws/orchestrator`（独立 Python 项目，本地跑）|
| 字体 | Quicksand（拉丁）+ HarmonyOS Sans SC（中文，base64 安装到 `public/fonts/`）|
| 主题 | LandingLayout，背景 `/images/bg1.jpg` |
| 路由 layout | `meta.layout: "landing"` |

---

## 七、Phase 2 起步建议

**新对话直接从这开始**：

1. 读本文档定调
2. 看 [Core 项目介绍.md](Core项目介绍.md) 拿后端协议
3. 第一个工作任务：写 `extensions/ai-block.ts` 的 Node 扩展骨架，打通 BubbleMenu 「讲解」按钮 → 在文档当前位置插入一个 `kind: 'placeholder'` 的 ai-block，3 秒后 mock 把它替换为 `kind: 'text'` 节点（模拟"流式占位 → 真实内容"流程）
4. 确认底层管道通了再批量做其它 NodeView

**核心原则**：
- 一个 TipTap Node 类型 + N 种 NodeView，靠 `attrs.kind` 路由分发
- 全部 NodeView 走 `<NodeViewWrapper>` Vue SFC 模式
- userState（答题/翻面）作为 attrs 一部分，TipTap 序列化时自动持久化
- 下次打开文档 setContent(html) 时，attrs 会还原回来

---

*Last updated: Phase 1 完成，Phase 2 待启动*
