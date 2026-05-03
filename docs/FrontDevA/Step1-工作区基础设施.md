# Step 1：工作区基础设施（前端 A）

> 这是会话/对话持久化设计的**第一阶段**：工作区元数据 + Sidebar 改造 + 背景图解耦。
>
> 第二阶段（Chat Session 持久化、接 F01 SSE）见 `Step2-Chat会话持久化.md`（待写）。

---

## 一、做了什么

### 0. 工作区背景图存储设计（重要）

桌面 App 思维：**用户上传的背景图复制到工作区目录的 `.assets/` 子目录下**。

```
<workspace.fsRoot>/
├── .assets/                ← 自动创建，存背景图等
│   ├── 6c4f...e2.jpg       ← UUID 命名避免冲突
│   └── a91b...d3.png
├── (用户的 Hyperdoc 文件)
└── tiles.json              ← 现有
```

数据库里的 `appearance.topBarBg` 存**相对路径**（如 `.assets/6c4f...e2.jpg`），渲染时通过 Electron IPC 读 buffer 转 blob URL 显示。

**好处**：
- 资源跟工作区目录"同行"（备份目录 = 备份资源）
- 不依赖后端，纯本地
- 文件丢失自动 fallback 默认图（不崩）

**触发链路**：

```
用户在 Dialog 选图（<input type="file">）
  ↓
读取 ArrayBuffer
  ↓
metaAgent.workspace.saveAssetTo({ targetRoot, buffer, originalName })
  ↓ (IPC)
Electron 主进程：复制到 <targetRoot>/.assets/<uuid>.<ext>
  ↓
返回 relPath = ".assets/xxx.jpg"
  ↓
存到 appearance.topBarBg

// 渲染时
useWorkspaceAsset(topBarBgRel, fsRootRef, fallback)
  ↓
检测到 ".assets/" 前缀 → metaAgent.workspace.readAssetFrom({ targetRoot, relPath })
  ↓ (IPC)
读 buffer → new Blob([buf]) → URL.createObjectURL(blob)
  ↓
设到 <img :src> / background-image
```

### 1.1 设计目标

按 V5 任务书 §1.4 信息架构：

```
Workspace（工作区，本阶段交付）
└─ Hyperdoc（文档元数据，本阶段表已建，CRUD API 已暴露）
   └─ ChatSession（Step 2 做）
      └─ ChatMessage（Step 2 做）
```

本阶段实现：
- **工作区元数据 CRUD**（SQLite 持久化 + REST API + 前端 Store + Dialog）
- **Sidebar 工作区折叠目录**（动态来源，可创建、点选切换）
- **背景图解耦**（BoardPage AppBar / LandingLayout 整页背景从写死改为读当前工作区 appearance）
- **路由 `/projects/:id`** 进入指定工作区
- **解耦文档与右下角 Chat** 浮窗（不再共享消息流）

### 1.2 不做什么（留给 Step 2）

- ❌ ChatSession 持久化（多 chat tab）
- ❌ Chat 消息持久化（不接 F01 SSE 的写库逻辑）
- ❌ Hyperdoc 自动注册（暂时仍由 Electron workspace IPC 用文件系统 scan，元数据表只存 API 暴露但未联动）
- ❌ 文档内 AI 节点重构（保持现有 TipTap AiBubbleNode）

---

## 二、产出文件清单

### Electron 端（2 IPC 改动）

| 文件 | 说明 |
|---|---|
| `TutorGridFront/electron/main.ts` (改) | 新增 `workspace:saveAssetTo` / `workspace:readAssetFrom` 两个 IPC handler |
| `TutorGridFront/electron/preload.ts` (改) | 暴露 `workspace.saveAssetTo` / `workspace.readAssetFrom` |

### 后端（3 文件 + 1 文件改动）

| 文件 | 说明 |
|---|---|
| `backend/workspace_meta/__init__.py` | 模块导出 |
| `backend/workspace_meta/store.py` | SQLite CRUD 层 |
| `backend/workspace_meta/service.py` | 业务封装（ID 生成、参数校验） |
| `backend/server/http_app.py` (改) | 注册 `workspace_router` + `hyperdoc_router` |

### 前端（5 新文件 + 5 文件改动）

| 文件 | 说明 |
|---|---|
| `TutorGridFront/src/stores/projectStore.ts` (新) | 工作区元数据 store + REST 调用 |
| `TutorGridFront/src/components/dialogs/CreateProjectDialog.vue` (新) | 创建工作区 Dialog（含图片上传 → IPC 保存到 .assets/） |
| `TutorGridFront/src/composables/useWorkspaceAsset.ts` (新) | 通用 hook：把 `.assets/xxx` 相对路径转 blob URL，支持 fallback |
| `TutorGridFront/src/components/navigation/WorkspaceSection.vue` (新) | Sidebar 工作区折叠区块 |
| `TutorGridFront/src/components/navigation/MainSidebar.vue` (改) | 引入 WorkspaceSection |
| `TutorGridFront/src/configs/navigation.ts` (改) | 移除 "Pages" 静态区块（被工作区动态目录替代） |
| `TutorGridFront/src/stores/workspaceStore.ts` (改) | 加 `setWorkspaceRoot` action（联动 Electron） |
| `TutorGridFront/src/views/pages/BoardPage.vue` (改) | AppBar 背景图响应当前工作区；监听路由 `/projects/:id` |
| `TutorGridFront/src/layouts/LandingLayout.vue` (改) | 整页背景图响应当前工作区 |
| `TutorGridFront/src/router/index.ts` (改) | 加 `/projects/:id` 路由 |
| `TutorGridFront/src/components/ai/ChatAssistant.vue` (改) | 浮窗 filter `origin === 'document'` 解耦 |

---

## 三、数据模型

### 3.1 SQLite 表（DB 文件：`scratch/storage/orchestrator.sqlite3`，与 memory/knowledge/sessions 共享）

```sql
CREATE TABLE workspaces (
  id            TEXT PRIMARY KEY,        -- ws_<12hex>
  name          TEXT NOT NULL,
  fs_root       TEXT NOT NULL,           -- Electron 选定的本地目录绝对路径
  appearance    TEXT NOT NULL DEFAULT '{}',  -- JSON: {topBarBg, pageBg, sidebarColor}
  created_at    INTEGER NOT NULL,        -- ms 时间戳
  updated_at    INTEGER NOT NULL
);

CREATE TABLE hyperdocs_meta (
  id              TEXT PRIMARY KEY,      -- doc_<12hex>
  workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title           TEXT NOT NULL,
  file_rel_path   TEXT NOT NULL,         -- 相对 fs_root 的相对路径
  created_at      INTEGER NOT NULL,
  last_edited_at  INTEGER NOT NULL
);

CREATE INDEX idx_hyperdocs_meta_workspace
ON hyperdocs_meta(workspace_id, last_edited_at DESC);
```

### 3.2 前端 TypeScript 类型

```ts
interface ProjectAppearance {
  topBarBg: string;       // BoardPage 顶部 AppBar 背景图 URL
  pageBg: string;         // LandingLayout 整页背景图 URL
  sidebarColor: string;   // Sidebar 折叠列表上的色块（可选 CSS 颜色）
}

interface Project {
  id: string;             // ws_xxx
  name: string;
  fsRoot: string;
  appearance: ProjectAppearance;
  createdAt: number;
  updatedAt: number;
}

interface HyperdocMeta {
  id: string;             // doc_xxx
  workspaceId: string;
  title: string;
  fileRelPath: string;
  createdAt: number;
  lastEditedAt: number;
}
```

---

## 四、REST API

**Base URL**：`http://127.0.0.1:8000`

### 4.1 工作区

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/workspaces` | 列出所有工作区 |
| GET | `/api/workspaces/{id}` | 获取单个工作区 |
| POST | `/api/workspaces` | 创建工作区 |
| PUT | `/api/workspaces/{id}` | 更新工作区 |
| DELETE | `/api/workspaces/{id}` | 删除工作区（级联删 hyperdocs） |

**POST `/api/workspaces` 请求体**：
```json
{
  "name": "数据挖掘",
  "fsRoot": "D:\\SoftInnovationCompetition\\TestFolder",
  "appearance": {
    "topBarBg": "https://example.com/header.jpg",
    "pageBg": "/images/bg2.jpg",
    "sidebarColor": "#d7e7ba"
  }
}
```

**响应**：
```json
{
  "id": "ws_a1b2c3d4e5f6",
  "name": "数据挖掘",
  "fsRoot": "D:\\SoftInnovationCompetition\\TestFolder",
  "appearance": { "topBarBg": "...", "pageBg": "...", "sidebarColor": "..." },
  "createdAt": 1746201234567,
  "updatedAt": 1746201234567
}
```

**PUT `/api/workspaces/{id}` 请求体**（任一字段可选）：
```json
{
  "name": "新名字",
  "appearance": { "topBarBg": "新URL", "pageBg": "", "sidebarColor": "" }
}
```

### 4.2 Hyperdoc 元数据

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/workspaces/{wsId}/hyperdocs` | 列出工作区下所有 Hyperdoc |
| POST | `/api/workspaces/{wsId}/hyperdocs` | 注册一个 Hyperdoc |
| DELETE | `/api/hyperdocs/{id}` | 删除元数据（实际文件由前端处理）|

**POST 请求体**：
```json
{
  "title": "线性回归实验",
  "fileRelPath": "hyperdocs/2026-05-02-linear-regression.hyper.json"
}
```

---

## 五、前端关键 API

### 5.1 `useProjectStore()`

```ts
const projectStore = useProjectStore();

// 列表
await projectStore.fetchList();
projectStore.list;                    // Project[]
projectStore.current;                 // Project | null
projectStore.currentAppearance;       // ProjectAppearance（fallback {})

// CRUD
await projectStore.createProject({ name, fsRoot, appearance });
await projectStore.updateProject(id, { name?, fsRoot?, appearance? });
await projectStore.deleteProject(id);

// 切换当前工作区（自动联动 workspaceStore.setWorkspaceRoot 切换 Electron 文件根）
await projectStore.setCurrent(id);

// Hyperdoc 元数据
await projectStore.fetchHyperdocs(projectId);
projectStore.hyperdocsByProject[projectId];  // HyperdocMeta[]
projectStore.hyperdocsOfCurrent;             // 当前工作区的 Hyperdoc
```

### 5.2 路由

```ts
// 跳转到指定工作区（会触发 BoardPage 自动 setCurrent）
router.push(`/projects/${projectId}`);
```

---

## 六、运行机制

### 6.1 进入工作区的完整链路

```
用户点击 Sidebar 工作区项（WorkspaceSection.vue）
    ↓
projectStore.setCurrent(id)
    ↓
1. projectStore.currentId = id
2. workspaceStore.setWorkspaceRoot(target.fsRoot)
   ├─ window.metaAgent.workspace.setRoot(newRoot)  ← Electron IPC
   └─ workspaceStore.init()  ← 重新加载磁贴/文件
    ↓
router.push(`/projects/${id}`)
    ↓
BoardPage 监听 route.params.id 变化
    ↓
appBarBg 计算属性自动取新工作区的 appearance.topBarBg
LandingLayout 整页背景同步切换 appearance.pageBg
```

### 6.2 文档/Chat 解耦机制

V5 spec 改进：现在浮窗只显示 chat 来源消息，文档内 AI 气泡不再"穿屏"出现在浮窗。

```
ChatAssistant.vue 浮窗渲染：
  messageStore.getSessionMessages(sessionId)
    .filter((m) => m.metadata?.origin !== "document")
                                ↑
                    新增过滤条件，砍掉文档侧消息
```

文档内 AI 气泡（TipTap AiBubbleNode）保持原有机制独立工作。Step 2 会进一步把消息 store 拆成独立 `chatMessageStore` + `chatSessionStore`。

---

## 七、验收教程

### 7.1 启动准备

```powershell
# 1. 后端跑起来
uvicorn backend.server.http_app:app --port 8000 --reload
# 或 Electron 自动 spawn

# 2. 前端
cd TutorGridFront
yarn dev
```

### 7.2 健康检查

打开浏览器或 PowerShell：

```powershell
curl http://127.0.0.1:8000/api/health
# 期望: {"status":"ok"}

curl http://127.0.0.1:8000/api/workspaces
# 期望: []  （首次启动是空数组）
```

### 7.3 验收测试清单

#### ✅ 测试 1：API 直接 CRUD

```powershell
# 创建一个工作区
curl -X POST http://127.0.0.1:8000/api/workspaces `
  -H "Content-Type: application/json" `
  -d '{"name":"测试工作区","fsRoot":"D:/test","appearance":{"topBarBg":"","pageBg":"","sidebarColor":"#d7e7ba"}}'
# 期望返回: {"id":"ws_xxx", ...}

# 列出
curl http://127.0.0.1:8000/api/workspaces
# 期望: [{...刚创建的}]
```

**通过条件**：返回结构跟 §四 文档一致。

#### ✅ 测试 2：Sidebar 显示工作区列表

1. 打开 Electron / 浏览器（dev mode 进 sidebar）
2. 左侧 sidebar 应该看到：
   - 顶部静态区：仪表盘 / 多人协作板 / 偏好设置 / Landing / UI
   - **底部新增："工作区"标题 + ➕ 按钮**
   - "工作区"下面显示测试 1 创建的项

**通过条件**：能看到工作区目录区块；如果无工作区，显示"点击 + 新建工作区"提示。

#### ✅ 测试 3：Dialog 创建工作区

1. 点 sidebar "工作区"右侧的 `+` 按钮
2. Dialog 弹出，含字段：名称 / 选择目录按钮 / "视觉外观"折叠区
3. 点"选择目录"→ Electron 弹文件夹选择对话框（仅 Electron 环境）
4. 选完目录、填名字、贴一张图片 URL，点"创建"
5. Dialog 关闭，sidebar 列表多出新项，**自动跳转到 `/projects/<新id>`**

**通过条件**：
- 创建成功 snackbar 提示
- 列表更新
- 路由跳转到 `/projects/:id`
- BoardPage 加载新工作区的磁贴

#### ✅ 测试 4：背景图解耦

**前置**：在测试 3 的 Dialog 里给 `topBarBg` 填一个图 URL（如 `https://picsum.photos/1200/300`），`pageBg` 填另一个（如 `https://picsum.photos/1920/1080`）。

进入工作区后：
- BoardPage 顶部 AppBar 背景应该是 `topBarBg` 那张
- 整页（v-main）背景应该是 `pageBg` 那张

**对照**：默认（无 appearance 配置时）：
- AppBar 背景 = `/images/boardbackground.jpg`
- 整页背景 = `/images/bg1.jpg`

**通过条件**：背景图随选中工作区切换。

#### ✅ 测试 5：持久化

1. 关掉 Electron / 刷新浏览器
2. 重新打开 → sidebar 工作区列表还在
3. 点工作区 → BoardPage 进入对应目录

**通过条件**：刷新后数据不丢。

#### ✅ 测试 6：文档/Chat 解耦

1. 进入任一 Hyperdoc 文档
2. 在文档里写一段 → AI 气泡（如果触发）只出现在文档流里
3. 打开右下角 Chat 浮窗 → **只显示 chat 自己的消息历史**，文档里的 AI 段落不会出现在浮窗

**通过条件**：浮窗与文档不再实时镜像同一份消息。

#### ✅ 测试 7：删除工作区（小心，不可逆）

```powershell
curl -X DELETE http://127.0.0.1:8000/api/workspaces/ws_xxx
```

或写一个 sidebar 右键菜单删除（**本阶段未做 UI**，仅 API 验证）。

**通过条件**：响应 `{"status":"ok"}`，sidebar 刷新后列表少一项。

---

## 八、已知限制 & Step 2 待办

### 限制

1. **Hyperdoc 元数据表已建但未自动联动**：
   - 现在 sidebar 折叠展开里 hyperdoc 列表来自 `/api/workspaces/{id}/hyperdocs`，但还没有"在文件系统创建 .hyper.json 时自动注册"的逻辑
   - 当前 BoardPage 内的磁贴系统仍走 `workspaceStore` 的文件 scan，与 hyperdocs_meta 表**双轨**
   - **临时**：sidebar 折叠下显示"暂无 Hyperdoc"

2. **删除 UI 缺失**：sidebar 上没有删工作区的按钮，需 API 直接删

3. **没有"编辑工作区"UI**：要改背景图只能 API PUT 或重新创建

### Step 2 待办

- ChatSession 持久化（多 tab 浮窗）
- F01 SSE 端点接受 `chat_session_id`，自动写入 `chat_messages` 表
- ChatFAB 浮窗加 session tabs
- 文档/Chat 完全解耦（拆出独立 chatMessageStore）
- Hyperdoc 元数据自动注册（创建 .hyper.json 时同步写表）

---

## 九、文件树速查

```
backend/
├── workspace_meta/             ← 新模块
│   ├── __init__.py
│   ├── store.py                ← SQLite 层
│   └── service.py              ← 业务封装
└── server/
    └── http_app.py             ← 注册 router

TutorGridFront/src/
├── stores/
│   ├── projectStore.ts         ← 新 store
│   └── workspaceStore.ts       ← 加 setWorkspaceRoot
├── components/
│   ├── dialogs/
│   │   └── CreateProjectDialog.vue   ← 新
│   ├── navigation/
│   │   ├── MainSidebar.vue          ← 引入 WorkspaceSection
│   │   └── WorkspaceSection.vue      ← 新
│   └── ai/
│       └── ChatAssistant.vue        ← filter origin
├── views/pages/
│   └── BoardPage.vue                ← AppBar 背景 + 路由参数
├── layouts/
│   └── LandingLayout.vue            ← 整页背景
├── router/
│   └── index.ts                     ← 加 /projects/:id
└── configs/
    └── navigation.ts                ← 删 Pages 区块
```

---

*维护：前端 A · 波 · Step 1 完成于 2026-05-02*
