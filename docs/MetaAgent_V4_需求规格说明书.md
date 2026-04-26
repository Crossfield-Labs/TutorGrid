# MetaAgent V4：磁贴式 AI 学习工作区

## 需求规格说明书（面向第 19 届中国大学生计算机设计大赛）

> **参赛大类：** 软件应用与开发 · (1) Web 应用与开发
>
> **赛题适配：** 运行在计算机、网络、数据库系统之上的软件，提供信息管理、信息服务等功能。参赛者须提供可在互联网上访问的网站地址。
>
> **项目团队：** Concrete.AI
>
> **文档版本：** V4 机设版 · 基于 V3 软创版演进

---

## 版本演进说明（V3 → V4）

| 维度 | V3（软创·安卓版） | V4（机设·PC 版） |
|------|-------------------|------------------|
| 主平台 | Android Compose + PC WinUI 3 | **Electron + Web（Vuetify3/Vue3）** |
| 赛事 | 第 19 届全国大学生软件创新大赛 | **第 19 届中国大学生计算机设计大赛 4C** |
| 产品形态 | 手机主入口 + 电脑执行端 | **PC 桌面端主入口（Web 亦可访问）** |
| 核心交互 | Chat 聊天界面 | **磁贴工作区 + TipTap 文档 + Chat** |
| 后端内核 | Python FastAPI + LangGraph（已跑通） | **直接复用 V3 内核，补齐前端** |
| 安卓端 | 主战场 | 暂搁置（软创过后再续） |

**核心原则：升级而非重来。** V3 后端编排引擎（19 个测试全通过）是项目核心资产，V4 侧重前端交互层重做 + 学习场景深化。

---

## 一、项目概述

### 1.1 一句话定位

> **MetaAgent 是一个会主动找你的磁贴式 AI 学习工作区。**
> 主导权完全在你手上，背后是一支基于 nanobot 改造的智能体团队在帮你做。

### 1.2 三大法宝

| 法宝 | 核心理念 | 落地形态 |
|------|---------|---------|
| **🔔 模型找你** | AI 不只被动等你提问，主动推送复习、催办、回调 | 磁贴自动生长 + 通知气泡 + 表情唤醒 |
| **🎮 主导权在你** | 你是主驾，AI 是副驾；以文档和工作区为载体 | Bento Grid 自由布局 + TipTap 共做文档 |
| **⚙️ 编排代理** | 没什么是中间件不能代替的；多 Agent 多 CLI 元调度 | LangGraph 编排引擎 + 多 Worker 委派 |

### 1.3 与竞品差异

| 对比维度 | NotebookLM | DeepTutor | ChatGPT/豆包 | **MetaAgent V4** |
|---------|-----------|-----------|-------------|-----------------|
| 产品本质 | 文档理解工具 | Agent 学伴（chat） | 通用对话引擎 | **磁贴式学习工作区** |
| 交互范式 | 单向问答 | 单向问答 | 单向问答 | **双向（AI 主动 + 用户主导）** |
| 学习载体 | PDF 查看器 | Chat 窗口 | Chat 窗口 | **TipTap 文档 + Bento 磁贴** |
| 代码/实验 | ❌ | Python 沙箱 | 基础代码执行 | **多 CLI 元调度（OpenCode/Codex/Aider）** |
| 记忆 | 无跨会话 | 基础会话 | 有限上下文 | **三层记忆 + 掌握度画像** |
| 空间感 | 无 | 无 | 无 | **用户自编排的可视化工作区** |

### 1.4 赛题适配说明

本作品投递**「软件应用与开发 · (1) Web 应用与开发」**小类：

- **B/S 模式**：前端为 Vue3 + Vuetify3 Web 应用（可通过浏览器访问），同时提供 Electron 桌面壳
- **可访问的网站地址**：部署后提供公网 IP / 域名
- **数据库系统**：SQLite 本地数据库 + 向量数据库（RAG 检索）
- **信息服务功能**：课程资料管理、智能检索、学习画像追踪、编排任务协作

---

## 二、需求分析

### 2.1 目标用户

**核心用户：** 中国 CS/SE 工科本科生（大二~大四）

- 课程资料多且分散（PPT/PDF/代码/录音散布于 QQ 群/学习通/微信群）
- 频繁使用电脑完成代码实验、整理报告
- 对效率提升和上下文连续性极度敏感
- 愿意折腾新工具，对 Electron 桌面端零心理负担

**扩展用户：** 一般理工科学生（数学/物理/电子等），有 PPT 复习 + 实验报告刚需但无代码需求。V4 不为其专门设计但不排斥。

### 2.2 六大痛点域

#### 痛点 ① 资料碎片化——"东一份西一份找不到"

老师 PPT 在 QQ 群、实验指导书在学习通、代码在 GitHub、板书照片在相册。**考前复习光"找资料"就消耗 30% 时间。**

#### 痛点 ② 复习效率低——"知道该复习但不知道从哪开始"

300 页 PPT 不知道哪些是重点、哪些已经会了。复习策略是"从头到尾看一遍"——效率最低的方法。

#### 痛点 ③ 实验/作业流程长——"不是不会，是串起来太慢"

一个 CNN 实验需要：读指导书→配环境→写代码→跑训练→调参→截图→写报告→交。每一步单独不难，串起来要 4-6 小时。

#### 痛点 ④ 单向交互——"所有 AI 都是我问它答"

现有 AI 全是被动的——用户不提问时 AI 就静默。但复习这件事本质上需要"被推着走"。

#### 痛点 ⑤ 使用门槛高——"配置环境比做实验还累"

大部分学生不会配 Python 环境。让他们 `pip install langchain` 然后写 `.env` = 直接劝退。

#### 痛点 ⑥ 学术合规——"用了 AI 会不会被判零分"

多所高校出台 AIGC 检测规范。产品叙事必须站在"帮你理解，不帮你写"的正确一侧。

### 2.3 需求优先级（MoSCoW）

#### 🔴 Must Have（P0·不做就别参赛）

| 编号 | 需求 | 对应痛点 | 说明 |
|------|------|---------|------|
| M1 | 课程知识库（多格式导入） | ① | PPT/PDF/Word/图片拖入即建索引 |
| M2 | RAG 精准问答 | ①② | "老师 PPT 第 42 页的观察者模式是什么？" |
| M3 | 磁贴工作区（Bento Grid） | 全部 | 用户自由布局学习桌面，所有功能的可视入口 |
| M4 | Chat 主界面（流式对话） | 全部 | WebSocket 实时推送，AI 流式回复 |
| M5 | 一键安装向导 | ⑤ | Electron 打包 + 首次启动填 API Key 引导 |
| M6 | TipTap 文档工作区 | ② | 以文档为载体的 AI 共做（笔记+产出+互动融合） |

#### 🟡 Should Have（P1·做了才能赢）

| 编号 | 需求 | 对应痛点 | 说明 |
|------|------|---------|------|
| S1 | 主动复习推送 | ④ | AI 根据知识库 + 掌握度主动出题/提醒 |
| S2 | PPT→思维导图→知识卡片 | ② | 一键把 300 页 PPT 结构化为可复习形态 |
| S3 | 编排树可视化 + Copilot 共做 | ③ | Plan Tree 可视化 + 用户审批 + 分步执行 |
| S4 | 实验 CLI 调度 | ③ | 主脑拆解实验 → OpenCode/Aider 执行代码部分 |
| S5 | 掌握度追踪 | ②④ | 记住"你哪里会了、哪里不会"，越用越精准 |
| S6 | 学习画像卡 | ②④ | 可视化展示在学课程、薄弱点、偏好、进度 |
| S7 | 消息气泡个性化 | ④ | 不同类型信息用不同气泡样式（提醒/汇报/鼓励） |

#### 🟢 Could Have（P2·锦上添花）

| 编号 | 需求 | 说明 |
|------|------|------|
| C1 | 仿题模式 | 上传真题出模拟卷 |
| C2 | 实验报告自动生成 | Copilot 共做产物自动排版 |
| C3 | 多课程工作区切换 | 每门课一个独立磁贴布局 |
| C4 | 待办/日程感知 | AI 主动催办截止日期 |
| C5 | Pin 图板 | 重要资料钉在工作区快速访问 |
| C6 | PDF.js 内嵌阅读器 | 磁贴内直接阅读 PDF + 页码跳转 |

#### 🔵 Won't Have（明确不做）

| 需求 | 理由 |
|------|------|
| 论文代写/降 AI 率 | 伦理死区 + 高校严查 |
| 安卓/iOS 移动端 | 本赛事聚焦 PC，移动端留给软创 |
| 通用 Agent 平台（Dify 式） | 不是产品定位 |
| GUI 自动化 | 太重，V3 已砍 |
| 通用闲聊 | ChatGPT/豆包已够 |

---

## 三、功能设计

### 3.1 功能架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  🖥️ Electron 壳 + Web 前端（Vuetify3 + Vue3 + TS）          │
│  ┌──────────────────────┐  ┌────────────────────────────┐   │
│  │  📌 磁贴工作区        │  │  💬 Chat 面板              │   │
│  │  Bento Grid 自由布局  │  │  WebSocket 流式对话        │   │
│  │  磁贴类型：           │  │  消息气泡个性化            │   │
│  │  ·PDF卡 ·便签        │  │  AI 表情/语气              │   │
│  │  ·思维导图 ·待办      │  │                            │   │
│  │  ·编排树入口          │  │                            │   │
│  │  ·AI主动推送卡        │  │                            │   │
│  └──────────┬───────────┘  └─────────────┬──────────────┘   │
│             │     TipTap 文档工作区       │                  │
│             └────────────┬───────────────┘                  │
└──────────────────────────┼──────────────────────────────────┘
                           │ WebSocket / REST
┌──────────────────────────▼──────────────────────────────────┐
│  🧠 MetaAgent 后端（FastAPI + Python）· 已有内核直接复用     │
│  ┌────────────────┐ ┌────────────────┐ ┌─────────────────┐  │
│  │ LangGraph      │ │ 记忆系统       │ │ RAG 检索引擎    │  │
│  │ 编排引擎       │ │ SQLite+Embed   │ │ 向量库+知识图谱 │  │
│  │ planning→      │ │ 短期/长期/画像 │ │ 课程空间索引    │  │
│  │ tools→verify→  │ │                │ │                 │  │
│  │ finalize       │ │                │ │                 │  │
│  └───────┬────────┘ └────────────────┘ └─────────────────┘  │
│          │ delegate_task                                     │
│  ┌───────▼────────────────────────────────────────────────┐  │
│  │ Worker 层（多 CLI 元调度）                              │  │
│  │ ·OpenCode Worker  ·Codex Worker  ·Claude Worker        │  │
│  │ ·CLI Runner       ·Local Python Runner                 │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 模块详细设计

#### 模块 F1：磁贴工作区（Bento Grid）

**定位：** 整个产品的主入口视图——空间化的学习桌面。

**磁贴类型：**

| 磁贴类型 | 尺寸选项 | 内容 | 交互 |
|---------|---------|------|------|
| PDF 卡 | 1×1 / 2×1 | PDF 缩略图 + 文件名 + 页码 | 双击进入 PDF.js 阅读器 |
| TipTap 便签 | 1×1 / 2×2 | 薄亚克力可编辑便签 | 直接编辑 + AI `/` 命令 |
| 思维导图 | 2×2 / 3×2 | AI 生成的知识结构图 | 展开/折叠节点 |
| 待办清单 | 1×1 | AI 或用户创建的任务列表 | 勾选完成 + AI 催办 |
| 编排树入口 | 1×1 / 2×1 | 当前任务编排树摘要 | 双击进入编排树全视图 |
| Chat 快照 | 1×1 | 重要对话片段的 Pin | 双击跳转对话上下文 |
| AI 推送卡 | 1×1 | AI 主动产出的复习建议/进度汇报 | 带呼吸灯标记"AI 主动" |
| 图片卡 | 1×1 / 2×2 | 课件截图/板书照片/结果图 | 双击放大 + OCR |
| 课程空间卡 | 2×1 | 某门课的资料概览 | 双击进入课程详情 |

**工作区操作：**

- Size / Padding 全局可调（滑块）
- 卡片自由拖拽排列
- JSON 持久化布局
- 右键菜单：调整大小 / 删除 / Pin/Unpin
- 文件夹可直接拖入批量导入磁贴

**AI 生长动画：** 当 AI 主动产出新磁贴时，磁贴从一个小点"啵"地展开到目标大小——视觉化"模型找你"。

#### 模块 F2：TipTap 文档工作区

**定位：** "以文档来互动和执行"的核心载体。

**功能：**

| 功能 | 说明 |
|------|------|
| 富文本编辑 | 完整 Markdown 支持 + 代码块高亮 + LaTeX 公式 |
| `/` AI 命令 | `/explain` 讲解选中内容 / `/quiz` 出题 / `/expand` 扩写 / `/summarize` 总结 |
| AI 内容块 | AI 产出嵌入文档中，可编辑、可折叠、可删除 |
| 编排树嵌入 | Plan Tree 节点完成后产物自动嵌入文档 |
| 拖拽互通 | 文档内容可拖出变磁贴；磁贴内容可拖入文档 |
| 协作标记 | 区分"用户写的"和"AI 写的"（颜色/图标） |
| 导出 | Markdown / PDF |

#### 模块 F3：Chat 面板

**定位：** 轻量级即时对话，与磁贴工作区和 TipTap 并存。

**功能：**

| 功能 | 说明 |
|------|------|
| 流式对话 | WebSocket 实时推送，token-by-token 渲染 |
| Chat/Agent 路由 | 简单问题 Chat 秒回，复杂任务自动切换 Agent 模式 |
| 消息气泡个性化 | 提醒/汇报/协商/鼓励 四种气泡样式 |
| AI 表情 | emoji + 语气词，像朋友发消息 |
| 上下文引用 | 点击引用跳转到 PPT/PDF 原文位置 |
| 拖出 Pin | 任意消息可拖到磁贴工作区成为 Pin |

#### 模块 F4：课程知识库

**定位：** 每门课程一个独立空间，承载所有课程资料 + RAG 索引。

**支持格式（优先级排序）：**

| 格式 | 解析方式 | 优先级 |
|------|---------|--------|
| PPT/PPTX | `python-pptx` 提取文本+图片 | 🔴 最高 |
| PDF | MinerU / PyMuPDF | 🔴 最高 |
| Word/DOCX | `python-docx` | 🟡 高 |
| Markdown/TXT | 直接读取 | 🟡 高 |
| 图片 | OCR（PaddleOCR） | 🟢 中 |
| Excel | `openpyxl` | 🔵 低 |

**RAG 流水线：**

```
文件导入 → 格式解析 → 分块(Chunking) → Embedding 向量化 → 存入向量库
                                                              ↓
用户提问 → Query 改写 → 混合检索(BM25+Dense) → Re-ranking → 上下文组装 → LLM 生成答案
```

**技术选型：**

- Embedding：`text-embedding-3-large`（OpenAI兼容接口）或国产替代
- 向量库：Chroma（本地轻量）或 FAISS
- 分块策略：递归字符分割 + 语义边界检测
- 检索优化：HyDE + Multi-Query + 混合检索

#### 模块 F5：编排引擎 + Copilot 共做

**定位：** V3 内核的核心能力，V4 直接复用。

**已有能力（内核现状）：**

- ✅ LangGraph 图：`planning → tools → verify → finalize`，含 `await_user` 节点
- ✅ Planner 能决定直接回答、调用工具、或强制收口
- ✅ 重复 tool call 抑制、最大迭代收口
- ✅ 工具层：`list_files / read_file / run_shell / web_fetch / await_user / delegate_task / delegate_opencode`
- ✅ 委派链路：`opencode / codex / claude` 之间选择、回退
- ✅ 会话快照：`status / phase / stopReason / activeWorker / awaitingInput`
- ✅ SQLite 持久化 + JSONL trace

**V4 需新增/补齐：**

| 补齐项 | 说明 | 优先级 |
|--------|------|--------|
| 前端编排树可视化 | Vue3 组件渲染 Plan Tree 节点状态 | P1 |
| 用户审批交互 | `await_user` 节点 → 前端弹审批卡 → WebSocket 回传 | P0 |
| 产物回传磁贴 | 子任务完成后产物自动生成磁贴 | P1 |
| 谦虚机制 UI | 低置信度时 AI 主动弹气泡询问 | P1 |

#### 模块 F6：记忆系统

**已有能力（内核现状）：**

- ✅ 会话历史压缩成摘要/facts/memory documents
- ✅ SQLite 存储 + 本地 embedding 检索
- ✅ 检索结果在 planning 前注入模型上下文

**V4 需新增：**

| 层级 | 记什么 | 怎么用 | 状态 |
|------|--------|--------|------|
| L1 用户偏好 | 输出风格、解释偏好 | 个性化回答和产物格式 | 需新增 |
| L2 课程上下文 | 在学课程、做过的实验、"模糊"标记 | RAG 增强、复习推荐 | 需新增 |
| L3 近期会话 | 最近决策、未完成事项、中断位置 | 跨会话连续性 | ✅ 已有 |
| L4 掌握度画像 | 每个知识点的掌握度评估 | 主动复习推送的依据 | 需新增 |

#### 模块 F7：主动推送系统

**定位：** "法宝一·模型找你"的技术落地。

| 推送类型 | 触发条件 | 前端表现 |
|---------|---------|---------|
| 复习提醒 | 掌握度低 + 超过遗忘周期 | 磁贴生长 + 通知气泡 |
| 任务催办 | 截止日期临近 + 任务未完成 | 待办磁贴高亮 |
| 结果回调 | 后台任务完成 | 新磁贴"啵"地出现 |
| 中断恢复 | 检测到未完成会话 | Chat 气泡提醒"要继续吗？" |

#### 模块 F8：安装向导

**定位：** "痛点⑤使用门槛"的直接解决方案。

**流程：**

```
下载 .exe/.dmg → 双击安装 → 启动 →
  ┌─ Step 1: 欢迎页 ─┐
  │ "30 秒完成配置"   │
  └─────┬────────────┘
        ↓
  ┌─ Step 2: 填 API Key ─┐
  │ DeepSeek / 智谱 / Qwen │
  │ 一键测试连通性          │
  └─────┬─────────────────┘
        ↓
  ┌─ Step 3: 创建第一个课程空间 ─┐
  │ 拖入一份 PPT 体验效果        │
  └─────┬───────────────────────┘
        ↓
  ┌─ Step 4: 进入工作区 ─┐
  │ 磁贴已就绪             │
  └────────────────────────┘
```

---

## 四、技术方案

### 4.1 技术选型总览

| 层级 | 方案 | 选型原因 |
|------|------|---------|
| **前端框架** | Vue 3 + Vuetify 3 + TypeScript | 团队已有 ChinaVis/磁贴项目积累，Vuetify Material Design 组件丰富 |
| **富文本编辑** | TipTap 2（ProseMirror） | Notion 同内核，插件生态强，Vue 官方支持好 |
| **磁贴布局** | 自研 Bento Grid（已有基座） | 团队已有多人协作看板底座，直接改造 |
| **PDF 渲染** | PDF.js | Mozilla 官方，浏览器内嵌阅读 |
| **桌面壳** | Electron | Web 代码直接跑，一套代码 Web+桌面两用 |
| **前后端通信** | WebSocket + REST | 实时流式事件 + 常规 CRUD |
| **后端框架** | FastAPI（Python 3.10+） | V3 内核已跑通，直接复用 |
| **编排引擎** | LangGraph StateGraph | 图状态机 + checkpoint + HIL + subgraph，V3 已实现 |
| **LLM 集成** | LangChain（LLM/Tool/Chain 抽象） | 与 LangGraph 同生态，工具调用标准化 |
| **可观测性** | LangSmith | Agent 链路追踪、token 成本监控、答辩展示 |
| **多 CLI 调度** | nanobot 改造的 Worker 系统 | V3 已打通 OpenCode/Codex/Claude 委派 |
| **RAG 向量库** | Chroma / FAISS | 本地优先，与 LangChain 集成成熟 |
| **文档解析** | MinerU（PDF）+ python-pptx（PPT）+ python-docx | 国产 MinerU 对中文科技文档友好 |
| **记忆存储** | SQLite + JSON + 本地 Embedding | V3 已有，本地优先 |
| **LLM 模型** | DeepSeek-V3 / 智谱 GLM-4 / Qwen（可切换） | 机设 2026 合规要求国产 AI |
| **数据存储** | SQLite + 文件工作区 | 本地优先，便于比赛展示和离线运行 |

### 4.2 LangGraph 编排引擎详解

**当前运行时流转（已实现）：**

```
用户输入
  ↓
SessionManager 创建会话 → 写 SQLite 初始快照
  ↓
SubAgentRunner → OrchestratorRuntime
  ↓
RuntimeState 初始化（planner + tools + memory + session）
  ↓
┌─ planning 节点 ─┐
│ 消费 follow-up   │
│ 检索长期记忆      │
│ 向 LLM 请求下一步 │
└───────┬──────────┘
        ↓
┌─ 条件路由 ─────────────────────────────┐
│ LLM 产出 tool calls → tools 节点执行    │
│ 证据足够 → 直接 finalize               │
│ 需要用户输入 → await_user 中断          │
│ 需要委派 → delegate_task → Worker 执行  │
└─────────────────────────────────────────┘
        ↓
Worker 进度/产物/权限 → 回写 session → 统一事件流
        ↓
session 完成 → memory compact → 可检索记忆
```

**LangGraph 关键特性使用：**

| 特性 | 用途 | 对应 V4 功能 |
|------|------|-------------|
| `StateGraph` + 条件边 | 编排树的动态路由 | Plan Tree 分支决策 |
| `interrupt()` / `await_user` | 人类审批中断 | 谦虚机制 + 用户审批 |
| `SqliteSaver` checkpointer | 状态持久化 + 崩溃恢复 | 断点续做 |
| Subgraph | 子 Agent 隔离执行 | 多 Worker 委派 |
| 流式输出 | token-by-token 推送 | Chat 面板实时渲染 |
| Memory Store | 跨会话记忆 | 学习画像持续积累 |

### 4.3 前后端通信协议

**WebSocket 端点：** `/ws/orchestrator`

**事件帧格式（JSON）：**

```json
{
  "type": "event",
  "event": "session.progress",
  "sessionId": "sess_xxx",
  "data": {
    "phase": "planning | tools | verify | finalize | await_user",
    "status": "running | paused | waiting_user | done | failed",
    "activeWorker": "opencode | codex | claude | null",
    "latestSummary": "正在分析实验指导书...",
    "progress": 0.35,
    "artifacts": []
  },
  "seq": 42,
  "timestamp": "2026-04-22T20:30:00Z"
}
```

**已支持的请求方法：**

| 方法 | 说明 |
|------|------|
| `session.start` | 创建新会话 |
| `session.input` | 用户发送消息/审批决策 |
| `session.cancel` | 取消当前任务 |
| `session.interrupt` | 中断执行 |
| `session.snapshot` | 获取当前快照 |
| `session.history` | 获取历史消息 |
| `session.list` | 列出所有会话 |
| `config.get / config.set` | 配置热更新 |
| `memory.compact` | 手动触发记忆压缩 |
| `memory.search` | 检索记忆 |

### 4.4 数据存储结构

```
data/
├── knowledge_bases/           # 课程知识库
│   └── {course_name}/
│       ├── raw/               # 原始文件（PPT/PDF/Word）
│       ├── parsed/            # 解析后的文本+图片
│       ├── chunks/            # 分块结果
│       └── index/             # 向量索引
├── sessions/                  # 会话数据（SQLite）
├── memory/                    # 记忆数据（SQLite + JSON）
├── workspaces/                # 磁贴工作区布局（JSON）
│   └── {workspace_id}.json
├── notebooks/                 # TipTap 文档（JSON）
├── user_profile/              # 学习画像（JSON）
└── logs/                      # 系统日志
```

---

## 五、核心场景设计

### 场景 A：期末复习周——"300 页 PPT 怎么啃"

1. 用户把 12 次课的 PPT 拖进「软体」课程空间磁贴
2. 等 2 分钟建完索引，思维导图磁贴自动"啵"地出现
3. 用户在 Chat 说"帮我出 5 道题测试水平"
4. AI 出题 → 用户答 → AI 精批 → 掌握度更新
5. 第二天 AI 主动推送磁贴："昨天管道-过滤器还没掌握，花 3 分钟做两道题？"

### 场景 B：实验 Copilot 共做

1. 用户说"帮我完成 CNN 实验，指导书在课程空间"
2. 编排树磁贴出现：6 步编排 + 审批按钮
3. 用户批准 → 后台执行 → 进度推送到 Chat + 磁贴更新
4. 关键步骤 AI 追问："你知道为什么选 ResNet 不选 VGG 吗？"
5. 做任务的过程变成学习的过程

### 场景 C：TipTap 文档共做

1. 用户在 TipTap 便签里记笔记"今天学了观察者模式"
2. 输入 `/explain` → AI 在文档内插入详细讲解
3. 输入 `/quiz` → AI 在文档内插入 3 道测验题
4. 用户做题 → AI 批改 → 结果嵌入文档
5. 整个学习过程在一个文档里闭环

---

## 六、项目分工参考

### 6.1 角色定义

| 角色 | 职责范围 |
|------|---------|
| **A. 产品主程/架构** | 产品设计 + 协议定义 + 系统架构 + 答辩文档 + Demo 编排 |
| **B. 前端开发** | Electron + Vue3 + Vuetify3 + TipTap + 磁贴工作区 |
| **C. 后端/AI 开发** | FastAPI + LangGraph + RAG + 记忆系统 + Worker 调度 |
| **D. 测试/部署/文档** | 集成测试 + Docker 打包 + 演示视频 + 用户手册 |

### 6.2 功能开发任务清单

#### 🖥️ 前端任务（角色 B 主导）

| 任务编号 | 任务名称 | 输入 | 产出 | 依赖 |
|---------|---------|------|------|------|
| FE-01 | Electron 壳 + 项目脚手架 | — | 可启动的 Electron + Vue3 项目 | 无 |
| FE-02 | 安装向导页 | UI 设计稿 | 4 步引导流程组件 | FE-01 |
| FE-03 | 磁贴工作区（Bento Grid） | 已有看板基座代码 | 可拖拽/调大小/持久化的磁贴容器 | FE-01 |
| FE-04 | 磁贴类型：PDF 卡 | PDF.js | 缩略图+页码+双击阅读 | FE-03 |
| FE-05 | 磁贴类型：TipTap 便签 | TipTap 2 | 可编辑便签 + `/` AI 命令 | FE-03 |
| FE-06 | 磁贴类型：待办清单 | — | 勾选+AI 催办 | FE-03 |
| FE-07 | 磁贴类型：AI 推送卡 | — | 呼吸灯+生长动画 | FE-03 |
| FE-08 | 磁贴类型：思维导图 | 可视化库（D3/Mermaid） | AI 生成的知识结构图 | FE-03 |
| FE-09 | 磁贴类型：编排树入口 | — | Plan Tree 节点状态渲染 | FE-03, BE-01 |
| FE-10 | Chat 面板 | WebSocket 协议 | 流式对话+气泡样式+表情 | FE-01, BE-02 |
| FE-11 | Chat 消息气泡个性化 | 设计规范 | 4 种气泡样式组件 | FE-10 |
| FE-12 | TipTap 文档工作区 | TipTap 2 + 插件 | 富文本+AI命令+产物嵌入 | FE-05 |
| FE-13 | TipTap AI 命令扩展 | TipTap Extension API | `/explain` `/quiz` `/expand` `/summarize` | FE-12, BE-03 |
| FE-14 | 拖拽互通（Chat↔磁贴↔文档） | Drag API | 内容可在三区域间拖拽 | FE-03,10,12 |
| FE-15 | 课程空间管理页 | — | 课程列表+文件上传+进度 | FE-03, BE-04 |
| FE-16 | 学习画像卡组件 | — | 在学课程/薄弱点/偏好可视化 | FE-03, BE-06 |
| FE-17 | 编排树全视图 | Vue Flow 或自研 | Plan Tree 可视化+审批交互 | FE-09, BE-01 |
| FE-18 | 主题/深色模式 | Vuetify3 主题系统 | 亮/暗切换 | FE-01 |

#### 🧠 后端/AI 任务（角色 C 主导）

| 任务编号 | 任务名称 | 输入 | 产出 | 依赖 |
|---------|---------|------|------|------|
| BE-01 | 内核对接：WebSocket 协议补齐 | V3 内核 | 前端可消费的完整事件流 | 无（内核已有） |
| BE-02 | Chat 流式输出适配 | LangGraph streaming | token-by-token WebSocket 推送 | BE-01 |
| BE-03 | TipTap AI 命令后端 | REST API | `/explain` `/quiz` 等端点 | BE-01 |
| BE-04 | 课程知识库 API | — | 文件上传+解析+RAG索引 CRUD | 无 |
| BE-05 | 多格式解析器 | MinerU+python-pptx+python-docx | PPT/PDF/Word→文本+图片 | BE-04 |
| BE-06 | 学习画像服务 | 记忆系统 | 掌握度追踪+画像读写 API | 内核记忆已有 |
| BE-07 | 主动推送调度器 | 画像+日程 | 定时检查→WebSocket 推送事件 | BE-06, BE-01 |
| BE-08 | RAG 检索优化 | LangChain Retriever | HyDE+Multi-Query+混合检索 | BE-04 |
| BE-09 | Worker 层：OpenCode 适配器 | V3 已有 | 补齐国产 LLM 接入（DeepSeek） | 内核已有 |
| BE-10 | Worker 层：本地 Python Runner | — | 安全沙箱跑实验脚本 | 内核已有 |
| BE-11 | 编排树产物→磁贴事件 | 内核 | 子任务完成→推送磁贴生成事件 | BE-01 |
| BE-12 | 记忆系统 L1/L2/L4 补齐 | V3 L3 已有 | 偏好层+课程层+掌握度层 | BE-06 |
| BE-13 | LangSmith 集成 | LangSmith SDK | Agent 链路追踪可视化 | BE-01 |

#### 📋 集成/部署任务（角色 D 或共同）

| 任务编号 | 任务名称 | 说明 |
|---------|---------|------|
| INT-01 | Electron 打包 | electron-builder 生成 .exe/.dmg |
| INT-02 | Docker Compose | 前后端一键启动 |
| INT-03 | 公网部署 | 提供可访问的网址（赛题要求） |
| INT-04 | 演示视频 | 不超过 10 分钟 |
| INT-05 | 答辩 PPT | 陈述+演示用 |
| INT-06 | 技术报告 | 赛事要求的作品文档 |
| INT-07 | 端到端测试 | 完整场景通过 |

#### 📝 产品/文档任务（角色 A 主导）

| 任务编号 | 任务名称 | 说明 |
|---------|---------|------|
| PM-01 | V4 产品书定稿 | 基于本文档迭代 |
| PM-02 | 协议文档 | WebSocket 帧格式+REST API 完整定义 |
| PM-03 | 磁贴类型设计规范 | 每种磁贴的视觉/交互/数据规范 |
| PM-04 | Demo 脚本编排 | 6 个场景的演示流程+故障预案 |
| PM-05 | 答辩叙事稿 | 10 分钟陈述逻辑 |

---

## 七、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 国产 LLM 效果不如 Claude/GPT | Agent 质量下降 | DeepSeek-V3 为主力（效果最接近），Qwen 备选；关键 Prompt 做针对性调优 |
| 磁贴工作区复杂度超预期 | 前端工期膨胀 | 已有看板基座，优先做 3 种核心磁贴（PDF/便签/推送卡），其余渐进 |
| PPT 解析丢失格式 | RAG 质量差 | python-pptx 提文本+MinerU 提图片双路径；复杂图表降级为截图 OCR |
| 编排引擎委派链路不稳定 | Demo 翻车 | 准备纯 Chat 模式的 fallback；Demo 用预演验证过的任务 |
| API Key 额度耗尽 | 答辩现场不可用 | 提前充值；准备离线录屏版 Demo |

---

## 八、参考文献

1. LangGraph — Build resilient language agents as graphs. MIT License. github.com/langchain-ai/langgraph
2. DeepTutor — AI-Powered Personalized Learning Assistant. HKUDS, HKU. AGPL-3.0. github.com/HKUDS/DeepTutor
3. TipTap — Headless rich text editor framework. tiptap.dev
4. Vuetify 3 — Vue Component Framework. vuetifyjs.com
5. MinerU — High-quality document parsing. Shanghai AI Lab. github.com/opendatalab/MinerU
6. LightRAG — Simple and Fast RAG. HKUDS. MIT. github.com/HKUDS/LightRAG

---

*MetaAgent V4 · 会主动找你的磁贴式 AI 学习工作区*
*Concrete.AI · 2026*
