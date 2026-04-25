# 前端知识库 + RAG + 记忆 详细测试文档

本文档用于你当前负责范围的前端联调测试，风格对齐我们之前后端测试流程：
- 每个用例都包含：`操作步骤`、`输入`、`期望输出`、`通过标准`
- 可按顺序直接执行

## 1. 测试目标

验证以下前端功能是否完整、可用、可回归：
- `知识库/RAG` 页：课程管理、文件入库、分块展示、RAG 查询、重嵌入、重建索引
- `记忆` 页：memory search、cleanup、reindex
- `设置` 页：LangSmith 配置读写
- 前后端协议链路：`orchestrator.config.get/set`、`orchestrator.knowledge.*`、`orchestrator.memory.*`

## 2. 测试前准备

### 2.1 目录与环境

- 仓库目录：`H:\Desktop\计设\pc_orchestrator_core`
- Python：建议 `.\.venv\Scripts\python.exe`
- 前端目录：`H:\Desktop\计设\pc_orchestrator_core\frontend`
- 后端 WS 地址：`ws://127.0.0.1:3210/ws/orchestrator`

### 2.2 测试样本建议

建议准备以下文件放在 `H:\Desktop\计设\samples\`：
- `docxDemo.docx`：包含“Observer pattern defines one-to-many dependency.”
- `pptDemo.pptx`：1 页文字
- `pdfDemo.pdf`：可提取文本
- `pngDemo.png`：图片里有英文或中文文字
- `docDemo.doc`：老格式 DOC

### 2.3 后端启动命令（联调模式）

```powershell
cd H:\Desktop\计设\pc_orchestrator_core

$env:ORCHESTRATOR_DOC_SOFFICE_BINARY="C:\Program Files\LibreOffice\program\soffice.exe"
$env:ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND="json"
$env:ORCHESTRATOR_MEMORY_INDEX_BACKEND="json"
$env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED="1"
$env:ORCHESTRATOR_RAG_MULTI_QUERY="1"
$env:ORCHESTRATOR_RAG_HYDE="1"
$env:ORCHESTRATOR_RAG_RERANK="1"
$env:ORCHESTRATOR_RAG_ANSWER_ENABLED="1"

.\.venv\Scripts\python.exe -m backend.main --host 127.0.0.1 --port 3210
```

期望输出：
- 控制台出现 `Orchestrator listening on ws://127.0.0.1:3210/ws/orchestrator`

### 2.4 前端启动命令

```powershell
cd H:\Desktop\计设\pc_orchestrator_core\frontend
npm run dev
```

期望输出：
- Vite 启动成功
- Electron/前端页面可打开

## 3. 测试用例（按顺序执行）

---

### TC-00 连接与页面基础状态

操作步骤：
1. 打开前端后观察顶部状态。
2. 观察是否有 `工作台 / 知识库/RAG / 记忆 / 设置` 四个页签。

输入：
- 无

期望输出：
- 连接状态显示 `已连接`
- 四个页签都可点击切换

通过标准：
- 满足以上 2 条

---

### TC-01 设置页读取配置（config.get）

操作步骤：
1. 进入 `设置` 页。
2. 观察 `模型与 API`、`LangSmith`、`记忆` 区域是否有默认值或回显值。

输入：
- 无

期望输出：
- 前端收到 `orchestrator.config.get`
- 页面字段被填充（不为空白异常状态）

通过标准：
- 设置页正常加载、无报错提示

---

### TC-02 设置页保存 LangSmith（config.set）

操作步骤：
1. 在 `设置 -> LangSmith` 中输入：
   - 启用开关：开
   - Project：`pc-orchestrator-core`
   - API Key：`test-key`（可用假值）
   - API URL：`https://api.smith.langchain.com`
2. 点击 `保存运行时设置`。
3. 重新切页后再回到设置页观察回显。

输入：
- 上述 4 个字段

期望输出：
- 收到 `orchestrator.config.set`
- 页面提示 `设置已保存。`
- LangSmith 字段回显与保存值一致

通过标准：
- 保存成功提示 + 回显一致

---

### TC-03 创建课程

操作步骤：
1. 切到 `知识库/RAG` 页。
2. 在左侧输入课程名称：`软件设计模式-前端测试`
3. 点击 `创建课程`

输入：
- 课程名：`软件设计模式-前端测试`
- 描述：`前端联调`

期望输出：
- 收到 `orchestrator.knowledge.course.create`
- 课程列表新增一条
- 新课程可被选中

通过标准：
- 列表中出现新课程并可选择

---

### TC-04 上传 DOCX 入库

操作步骤：
1. 选择刚创建课程。
2. 在 `文件入库` 使用 `浏览` 或粘贴路径：`H:\Desktop\计设\samples\docxDemo.docx`
3. 点击 `开始入库`
4. 点击 `刷新文件/分块/任务`

输入：
- filePath：`...docxDemo.docx`
- chunkSize：`900`

期望输出：
- 事件 `orchestrator.knowledge.file.ingest`
- `payload.status = success`
- `chunkCount > 0`
- 文件列表出现该文件，解析器在分块中为 `python-docx`

通过标准：
- 文件、任务、分块三处都能看到入库结果

---

### TC-05 上传 PNG（OCR）入库

操作步骤：
1. 在同一课程上传 `H:\Desktop\计设\samples\pngDemo.png`
2. 入库后刷新数据

输入：
- filePath：`...pngDemo.png`

期望输出：
- `status = success`
- 分块列表出现 OCR 文本
- `metadata.parser` 为 `paddleocr` 或 `rapidocr`

通过标准：
- 能看到可读 OCR 文本块

---

### TC-06 上传 DOC 入库（老格式）

操作步骤：
1. 上传 `H:\Desktop\计设\samples\docDemo.doc`
2. 入库后刷新

输入：
- filePath：`...docDemo.doc`

期望输出：
- 成功时：`status=success` 且 chunk 文本可读
- 失败时：明确错误包含后端缺失详情（antiword/catdoc/soffice/Word COM）

通过标准：
- 成功或可解释失败（二者任选其一，但不能静默失败）

---

### TC-07 分块与解析器验证

操作步骤：
1. 查看 `分块与解析器` 面板。
2. 随机抽查 3 个 chunk。

输入：
- 无

期望输出：
- 每个 chunk 有 `content`
- `parser` 字段与来源文件类型匹配
- 不出现大段二进制乱码

通过标准：
- 抽查通过

---

### TC-08 RAG 查询（含答案与调试）

操作步骤：
1. 在 `RAG 查询` 输入：`Observer pattern 核心思想是什么？`
2. 点击 `查询`

输入：
- query：`Observer pattern 核心思想是什么？`
- limit：`8`

期望输出：
- 事件 `orchestrator.knowledge.rag.query`
- `items` 非空
- 页面 `答案` 区域有文本（或显示“仅返回检索片段”）
- 调试区域能看到：
  - `answerSource`
  - `hydeSource`
  - 若失败有 `answerError/hydeError`

通过标准：
- 至少命中 1 个相关 chunk 且调试信息可读

---

### TC-09 课程重嵌入

操作步骤：
1. 在 `课程重嵌入` 区域点击 `执行重嵌入`

输入：
- batchSize：`32`

期望输出：
- 事件 `orchestrator.knowledge.course.reembed`
- `updatedCount >= 0`
- `chunkCount >= 0`
- 有 `dimensions` 与 `indexBackend`

通过标准：
- 事件成功返回且统计字段完整

---

### TC-10 课程重建索引

操作步骤：
1. 点击 `重建课程索引`

输入：
- 无（基于当前课程）

期望输出：
- 事件 `orchestrator.knowledge.course.reindex`
- 返回 `indexBackend`、`chunkCount`、`dimensions`

通过标准：
- 返回成功，无异常提示

---

### TC-11 记忆检索

操作步骤：
1. 切到 `记忆` 页。
2. 输入 `Search query`：`Observer pattern`
3. 点击 `Search`

输入：
- query：`Observer pattern`
- limit：`8`

期望输出：
- 事件 `orchestrator.memory.search`
- 结果区显示列表（可为空，但请求必须成功）

通过标准：
- 请求成功 + 页面无异常

---

### TC-12 记忆整理与重建

操作步骤：
1. 在 `记忆` 页点击 `Cleanup Memory`
2. 点击 `Reindex Memory`

输入：
- 无

期望输出：
- `orchestrator.memory.cleanup` 成功
- `orchestrator.memory.reindex` 成功
- 有成功提示

通过标准：
- 两个动作都能完成

---

### TC-13 删除文件后回归验证

操作步骤：
1. 在知识库文件列表中删除一条文件记录
2. 刷新文件/分块/任务
3. 再次执行同一个 RAG 查询

输入：
- 删除目标：任一 `fileId`

期望输出：
- `orchestrator.knowledge.file.delete` 成功
- 被删文件 chunk 消失
- RAG 命中结果发生合理变化

通过标准：
- 删除结果可见且检索结果同步变化

## 4. 一键脚本测试（推荐）

脚本路径：`scripts/e2e_kb_rag_memory.py`

示例命令：

```powershell
cd H:\Desktop\计设\pc_orchestrator_core

.\.venv\Scripts\python.exe .\scripts\e2e_kb_rag_memory.py `
  --ws-url ws://127.0.0.1:3210/ws/orchestrator `
  --course-name "smoke-course-frontend" `
  --course-description "frontend smoke" `
  --file-path "H:\Desktop\计设\samples\docxDemo.docx" `
  --file-path "H:\Desktop\计设\samples\pngDemo.png" `
  --query "Observer pattern 核心思想是什么？" `
  --set-langsmith `
  --langsmith-enabled 1 `
  --langsmith-project "pc-orchestrator-core"
```

期望输出：
- 控制台出现多条 `[ok] event=...`
- 最后有 `[final-summary]` JSON，至少包含：
  - `courseId`
  - `fileCount/chunkCount`
  - `ragHitCount`
  - `reembed/courseReindex/memoryReindex`

## 5. 常见失败与定位

### 5.1 后端起不来

现象：
- 前端一直 `未连接`

排查：
- 看后端报错是否缺模块（如 `sqlalchemy`）
- 确认启动命令在项目根目录执行

### 5.2 PNG 入库失败（OCR）

现象：
- `PaddleOCR is required...`

排查：
- 安装 OCR 依赖或切换 RapidOCR

### 5.3 DOC 入库失败

现象：
- `DOC parsing failed... binary not found`

排查：
- 配置 `ORCHESTRATOR_DOC_SOFFICE_BINARY`
- 确认 LibreOffice 安装并可执行

### 5.4 RAG 没有答案

现象：
- 有 items 但 answer 空

排查：
- 看调试字段 `answerSource/answerError/hydeSource/hydeError`
- 检查 LLM/embedding 配置和可用性

## 6. 测试记录模板（建议）

每条用例记录：
- `用例ID`
- `执行时间`
- `输入`
- `实际输出`
- `是否通过`
- `问题定位`
- `修复后回归结果`

