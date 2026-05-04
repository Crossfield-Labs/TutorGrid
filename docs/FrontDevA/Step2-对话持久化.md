# Step 2：对话持久化（前端 A · 全栈）

> 接 Step 1（工作区基础设施）。本阶段把右下角 Chat 浮窗改造成"**多会话 + 持久化**"，并打通文档 ↔ Chat 的跨视图同步。

---

## 一、做了什么 / 不做什么

### 做了 ✅

**核心 7 项（持久化叙事）**
1. 后端 SQLite 表：`chat_sessions` + `chat_messages`
2. 后端 REST：`/api/hyperdocs/{id}/chats` + `/api/chats/{id}/messages`
3. F01 SSE 端点改造：自动写入 user 消息 + AI 完整回复（前端不重复写）
4. 前端 `chatSessionListStore`：管理"某 hyperdoc 下所有 chat sessions"
5. 前端 `chatMessageStore`：拉历史 + SSE 实时 append（独立于 messageStore）
6. ChatAssistant 加 session tabs（顶部 chip 切换 + ➕ 新建）
7. 进 Hyperdoc 自动 ensureDefault：没 session 就建一个默认会话

**跨视图同步（V5 spec §2.5.3）**
8. AI 消息 → "📌 插入到文档" 按钮
9. AiBubble → "💬 在 Chat 中讨论" 按钮

**Step 1 边缘待办（顺手做掉）**
10. Hyperdoc 元数据自动注册：addHyperdoc 时同步 POST 写 `hyperdocs_meta`
11. 编辑工作区 Dialog（改名 / 换背景图）
12. Sidebar 工作区 hover 显示菜单（编辑 / 删除）+ 删除确认
13. sidebarColor 渲染验证：在工作区行 append 位置显示色块圆点
14. messageStore 角色注释收窄：明确只服务 F07 文档气泡，不再服务浮窗

### 不做 ❌

- **不动文档内 AI 气泡（F07）**：DocumentEditor + AiBubbleNode 仍走 messageStore（内存）
- **不重写 ChatAgent**：仍用现有的 `backend/agent`
- **chat session 无法跨 hyperdoc**：每条 chat 必须绑一个 hyperdoc

---

## 二、产出文件清单

### 后端（3 新 + 2 改）

| 文件 | 说明 |
|---|---|
| `backend/chats/__init__.py` (新) | 模块导出 |
| `backend/chats/store.py` (新) | SQLite CRUD（chat_sessions + chat_messages）|
| `backend/chats/service.py` (新) | 业务封装（ID 生成、ensure_session 等）|
| `backend/server/http_app.py` (改) | 注册 chats_router + 5 个 chat REST 端点 |
| `backend/server/chat_api.py` (改) | SSE 端点自动写库（user 消息进流前写、AI 消息流结束后写）|

### 前端（4 新 + 6 改）

| 文件 | 说明 |
|---|---|
| `TutorGridFront/src/stores/chatSessionListStore.ts` (新) | chat sessions 列表管理 |
| `TutorGridFront/src/stores/chatMessageStore.ts` (新) | chat 消息持久化 + SSE 实时态 |
| `TutorGridFront/src/composables/useDocumentEditorBus.ts` (新) | 全局 EditorBus，让浮窗能反向调当前 TipTap editor |
| `TutorGridFront/src/components/dialogs/EditProjectDialog.vue` (新) | 编辑工作区 |
| `TutorGridFront/src/components/ai/ChatAssistant.vue` (改) | session tabs + 数据源切到新 store + "插入到文档"按钮 |
| `TutorGridFront/src/components/navigation/WorkspaceSection.vue` (改) | hover 菜单（编辑/删除）+ sidebarColor 显示 |
| `TutorGridFront/src/views/document/components/DocumentEditor.vue` (改) | mounted 时把 editor 注册到 EditorBus |
| `TutorGridFront/src/views/document/extensions/ai-views/AiBubble.vue` (改) | 加"💬 在 Chat 中讨论"按钮 |
| `TutorGridFront/src/stores/workspaceStore.ts` (改) | addHyperdoc 时同步注册元数据到后端 |
| `TutorGridFront/src/stores/messageStore.ts` (改) | 顶部注释更新（角色收窄说明）|

---

## 三、数据模型

### 3.1 SQLite 表（DB 文件复用 `scratch/storage/orchestrator.sqlite3`）

```sql
CREATE TABLE chat_sessions (
  id              TEXT PRIMARY KEY,        -- chat_<12hex>
  hyperdoc_id     TEXT NOT NULL,           -- 绑定的 hyperdoc id（业务约束，不强外键）
  title           TEXT NOT NULL DEFAULT '默认会话',
  created_at      INTEGER NOT NULL,        -- ms 时间戳
  last_active_at  INTEGER NOT NULL
);
CREATE INDEX idx_chat_sessions_hyperdoc
  ON chat_sessions(hyperdoc_id, last_active_at DESC);

CREATE TABLE chat_messages (
  id          TEXT PRIMARY KEY,            -- msg_<12hex>
  session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,               -- user | ai | system
  content     TEXT NOT NULL,
  metadata    TEXT NOT NULL DEFAULT '{}',  -- JSON: {citations, toolsUsed, origin, sourceNodeId, ...}
  timestamp   INTEGER NOT NULL
);
CREATE INDEX idx_chat_messages_session
  ON chat_messages(session_id, timestamp ASC);
```

### 3.2 前端 TypeScript 类型

```ts
interface ChatSessionItem {
  id: string;             // chat_xxx
  hyperdocId: string;
  title: string;
  createdAt: number;
  lastActiveAt: number;
}

interface ChatMessage {
  id: string;             // 后端持久化的 msg_xxx，或前端临时态 u_xxx/a_xxx
  sessionId: string;
  role: "user" | "ai" | "system";
  content: string;
  metadata?: ChatMessageMetadata;
  timestamp: number;
  // 仅本地态（不写库）
  streaming?: boolean;
  errored?: boolean;
}

interface ChatMessageMetadata {
  citations?: ChatCitation[];
  toolsUsed?: string[];
  searchResults?: Array<...>;
  origin?: "chat" | "document";  // 来源（document = 跨视图引用）
  sourceNodeId?: string;          // 文档→Chat 引用时的源 AiBubble id
}
```

---

## 四、REST API

**Base URL**：`http://127.0.0.1:8000`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/hyperdocs/{hyperdocId}/chats` | 列出 hyperdoc 下所有 chat session |
| POST | `/api/hyperdocs/{hyperdocId}/chats` | 新建 session，body `{title?}` |
| GET | `/api/chats/{sessionId}` | 单个 session |
| PUT | `/api/chats/{sessionId}` | 改名，body `{title}` |
| DELETE | `/api/chats/{sessionId}` | 删 session（级联删消息） |
| GET | `/api/chats/{sessionId}/messages?limit=200` | 列消息（按时间正序） |
| POST | `/api/chats/{sessionId}/messages` | 兜底写消息（一般 SSE 自动写）|

**SSE 端点**（F01 改造）：

```jsonc
POST /api/chat/stream
{
  "session_id": "chat_xxx",   // ← Step 2：必须是 chat_sessions.id（前端从 chatSessionListStore 拿）
  "message": "...",
  "context": { "doc_id": "hyper_xxx" }  // ← 用作 chat_session.hyperdoc_id 兜底
}
```

后端会**自动**：
1. ensureSession（若不存在则创建）
2. 写入 user message（写流前）
3. 流结束后写入完整 ai message（含 toolsUsed / citations metadata）

---

## 五、关键链路

### 5.1 进 Hyperdoc → 加载默认会话

```
用户进入 Hyperdoc
  ↓
HyperdocPage.onMounted → chatSession.setSession(legacyId, docId)
  ↓
ChatAssistant watch(currentDocId) → ensureDefault(docId)
  ├─ fetchByHyperdoc → 后端返回该 doc 下所有 chat session 列表
  ├─ 列表为空 → POST 新建一个 "默认会话"
  └─ 设 currentSessionId = first.id（覆盖 legacyId）
  ↓
fetchBySession(currentSessionId) → 拉历史消息显示
```

### 5.2 发送消息 + 持久化

```
用户输入 → sendMessage()
  ├─ chatMessageStore.pushUserMessage（立即本地显示）
  ├─ chatMessageStore.startAiPlaceholder（占位气泡 streaming=true）
  └─ streamChat({ session_id, message, context.doc_id }) ← 触发后端 SSE
       ↓
后端 chat_api.py
  ├─ ensure_session(session_id, hyperdoc_id)
  ├─ append_message(role=user)  ← 持久化用户消息
  └─ stream_chat agent → SSE 流
       前端 onEvent 处理
         ├─ delta → appendDelta（实时打字效果）
         ├─ tool_call → addToolUsed
         ├─ tool_result → addCitations / addSearchResults
         ├─ done → finishAi
         └─ error → failAi
       SSE 流结束
         ↓
后端 chat_api finally
  └─ append_message(role=ai, content=full, metadata={tools, citations, ...}) ← 持久化 AI 消息
```

刷新浏览器后调 `fetchBySession` 重新拉，能看到完整历史。

### 5.3 跨视图同步：Chat → 文档

```
浮窗 AI 消息上点"📌 插入到文档"
  ↓
ChatAssistant.insertToDocument()
  ↓
editorBus.insertAiBubble({ content })
  ↓
（DocumentEditor onMounted 已 register 当前 editor 到 bus）
当前 TipTap editor.chain().insertContent(blockquote)
  ↓
文档里多出一个 "💬 来自 Chat: ..." 引用块
```

### 5.4 跨视图同步：文档 → Chat

```
文档 AiBubble 节点上点 mdi-comment-outline
  ↓
AiBubble.onDiscussInChat()
  ↓
chatMessageStore.pushQuoteFromDocument(currentSessionId, "> ...", sourceNodeId)
  ├─ 立即在浮窗显示一条 user 消息（含引用文）
  └─ POST /api/chats/{id}/messages 持久化（origin=document）
  ↓
用户在浮窗输入框继续提问 → 走正常 SSE 流
```

---

## 六、验收教程

### 6.1 启动

```powershell
# 后端（自动建表 chat_sessions / chat_messages）
uvicorn backend.server.http_app:app --port 8000 --reload

# 前端
cd TutorGridFront
yarn dev
```

### 6.2 验收测试清单（10 条）

#### ✅ 测试 1：表自动建好

```powershell
sqlite3 scratch/storage/orchestrator.sqlite3 ".tables"
# 期望: workspaces hyperdocs_meta chat_sessions chat_messages 都能看到
```

#### ✅ 测试 2：API CRUD 直测

```powershell
# 假设已经有一个 hyperdoc，比如 hyper_test
curl -X POST http://127.0.0.1:8000/api/hyperdocs/hyper_test/chats `
  -H "Content-Type: application/json" `
  -d '{"title":"公式推导"}'
# 期望返回: {"id":"chat_xxx","hyperdocId":"hyper_test","title":"公式推导",...}

curl http://127.0.0.1:8000/api/hyperdocs/hyper_test/chats
# 期望: [{...刚创建的}]
```

#### ✅ 测试 3：进 Hyperdoc 自动建默认会话

1. 进入任一 Hyperdoc 文档（路由 `/hyperdoc/:id`）
2. 右下角点开 Chat 浮窗
3. **预期**：顶部 tab 区域出现一个"默认会话" chip，自动选中

后端 SQLite 检查：
```powershell
sqlite3 scratch/storage/orchestrator.sqlite3 "SELECT * FROM chat_sessions WHERE hyperdoc_id='<docId>'"
# 期望：至少 1 行
```

#### ✅ 测试 4：发消息 → 自动持久化

1. 浮窗里发一条消息"线性回归是什么"
2. 等 AI 回复完成
3. 关闭浮窗，**刷新浏览器**
4. 重新进文档 + 打开浮窗
5. **预期**：消息历史还在（user + AI 两条）

后端 SQLite 检查：
```powershell
sqlite3 scratch/storage/orchestrator.sqlite3 "SELECT role, content FROM chat_messages ORDER BY timestamp"
# 期望：user "线性回归是什么" + ai 完整回复
```

#### ✅ 测试 5：多 session 切换

1. 浮窗里点 ➕ → 自动新建会话，命名"默认会话"
2. 顶部 chip 区出现 2 个 tab，新会话被选中
3. 在新会话里发消息
4. 切回旧会话 chip
5. **预期**：消息列表切换，互不污染

#### ✅ 测试 6：Chat → 文档（插入按钮）

1. AI 给出回复后
2. 该 AI 消息底部出现"📌 插入到文档"按钮（仅当文档编辑器活跃时显示）
3. 点击 → 文档当前光标位置插入一个 blockquote："💬 来自 Chat: ..."
4. **预期**：文档里看到引用块

#### ✅ 测试 7：文档 → Chat（讨论按钮）

1. 在文档里用 slash 命令触发一个 AI 气泡（如 `/explain`）
2. AI 气泡完成后，meta 行的右侧出现 mdi-comment-outline 按钮
3. 点击 → 浮窗 message-container 出现一条引用消息（含"> 文档段落..."）
4. **预期**：snackbar 提示"已加入当前会话"

#### ✅ 测试 8：Hyperdoc 元数据自动注册（#10）

1. 选中一个工作区 → 进入 BoardPage
2. 在某列点 + 创建新 Hyperdoc → 输入标题"测试文档" → 创建
3. 看 Sidebar 折叠展开里
4. **预期**：该工作区下出现"测试文档"项

后端检查：
```powershell
sqlite3 scratch/storage/orchestrator.sqlite3 "SELECT title, file_rel_path FROM hyperdocs_meta"
```

#### ✅ 测试 9：编辑/删除工作区 UI（#11/#12）

1. Sidebar 工作区行 hover → 右侧出现 ⋮ 菜单按钮
2. 点 ⋮ → "编辑" → 弹出 EditProjectDialog → 改名/换背景图 → 保存
3. **预期**：sidebar 名字变了，BoardPage 背景换了
4. 再点 ⋮ → "删除" → 确认 Dialog → 确认
5. **预期**：sidebar 列表少一项，路由跳回 /board

#### ✅ 测试 10：sidebarColor 显示（#13）

1. 创建工作区时填 `sidebarColor: #d7e7ba`
2. **预期**：Sidebar 该工作区行右侧出现一个浅绿色圆点

---

## 七、跟 Step 1 整合的全景图

```
Sidebar
├─ 功能区（仪表盘 / Board / 设置 / Landing / UI）
└─ 工作区折叠列表 ← 来源 projectStore (Step 1)
   ├─ ▼ 数据挖掘 [⋮]            ← hover 显示菜单（编辑/删除）Step 2
   │  ├─ 📄 线性回归实验        ← 来源 hyperdocs_meta（Step 2 #10 自动注册）
   │  └─ 📄 决策树作业
   └─ ▶ 机器学习 [⋮]

进入 Hyperdoc → 右下角 ChatFAB（Step 2）
└─ 浮窗
   ├─ 顶部 tabs（chat session 切换 + ➕）   ← chatSessionListStore
   ├─ 消息流                                ← chatMessageStore
   │  ├─ 用户消息
   │  └─ AI 消息 [📌 插入到文档]            ← Step 2 #8
   └─ 输入框 → SSE → 自动持久化              ← chat_api.py 改造

文档区 AiBubbleNode (F07，不动)
├─ 用户气泡
└─ AI 气泡 [💬 在 Chat 中讨论] [×]         ← Step 2 #9
```

---

## 八、已知限制 & Step 3 待办

| 限制 | 影响 | 后续 |
|---|---|---|
| 文档级 AI 气泡的 SSE 也会写 chat_messages 表 | 库里会有"虚假 chat session"（id=tile.metadata.sessionId）| Step 3 把文档级 AI 内容序列化到 .hyper.json，不写库 |
| chat session 必须绑 hyperdoc | 没有"全局 chat" | Step 3 加 `hyperdoc_id NULL` 支持 |
| 浮窗 session 没有"重命名"UI | 只能 API 改 | Step 3 加 chip 长按改名 |
| 删除工作区不删 .assets/ 里的图 | 残留文件 | Step 3 IPC 加 cleanupAssets |
| messageStore 没真正删除 | 仍占内存 | F07 文档气泡的最终去向定了再删 |

---

## 九、文件树速查

```
backend/
├── chats/                          ← 新模块
│   ├── __init__.py
│   ├── store.py                    ← SQLite 层
│   └── service.py                  ← 业务封装
└── server/
    ├── http_app.py                 ← 注册 chats_router
    └── chat_api.py                 ← SSE 自动写库

TutorGridFront/src/
├── stores/
│   ├── chatSessionListStore.ts     ← 新（session 列表）
│   ├── chatMessageStore.ts         ← 新（消息持久化）
│   ├── messageStore.ts             ← 注释收窄（F07 文档气泡专用）
│   └── workspaceStore.ts           ← addHyperdoc 同步注册元数据
├── composables/
│   └── useDocumentEditorBus.ts     ← 新（跨视图 EditorBus）
├── components/
│   ├── dialogs/
│   │   └── EditProjectDialog.vue   ← 新
│   ├── navigation/
│   │   └── WorkspaceSection.vue    ← hover 菜单 + sidebarColor
│   └── ai/
│       └── ChatAssistant.vue       ← session tabs + 新 store + 插入按钮
└── views/document/
    ├── components/
    │   └── DocumentEditor.vue      ← register editor 到 bus
    └── extensions/
        └── ai-views/
            └── AiBubble.vue        ← "在 Chat 中讨论"按钮
```

---

*维护：前端 A · 波 · Step 2 完成于 2026-05-03*
