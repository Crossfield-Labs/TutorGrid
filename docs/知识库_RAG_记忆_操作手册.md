# 知识库 + RAG + 记忆 操作与测试手册

本文档面向 `pc_orchestrator_core` 当前后端实现，覆盖你负责范围内的核心能力：
- 课程知识库 API（创建、入库、查询、删除、重嵌入、重建索引）
- 多格式解析（`.doc/.docx/.pptx/.pdf/.png/.jpg/.jpeg/.bmp/.webp/.md/.txt`）
- RAG 优化链路（Multi-Query + HyDE + 混合检索 + rerank + answer）
- Memory 检索与索引重建
- 常见故障定位与可执行测试清单

## 1. 总体流程（你关心的 3.1~3.4）

### 1.1 3.1 创建课程（元数据层）
- 调用 `orchestrator.knowledge.course.create`。
- 后端写入 SQLite：`scratch/storage/orchestrator.sqlite3` 的 `knowledge_courses` 表。
- 返回 `courseId`，后续所有入库和查询都基于这个 `courseId`。

### 1.2 3.2 文件入库（原文件落盘）
- 调用 `orchestrator.knowledge.file.ingest`，传 `courseId + filePath (+ fileName)`。
- 后端把源文件复制到：
  - `data/knowledge_bases/<courseId>/raw/<文件名_文件大小.扩展名>`
- 同时写入 SQLite：
  - `knowledge_files`（文件记录）
  - `knowledge_jobs`（入库任务状态）

结论：3.2 的核心是“原文件落盘 + 任务记录创建”。

### 1.3 3.3 分块与向量化（可检索数据层）
- 入库流程内部会自动执行：
  - 解析器提取文本块（`ParsedBlock`）
  - `ChunkBuilder` 按 `chunkSize` 切分
  - 计算 embedding（真实 embedding 或 fallback）
  - 写入 `knowledge_chunks`
  - 触发课程索引重建（FAISS/Chroma/JSON）

结论：分块后持久化的是“文本块 + 元数据 + 向量”，不是原二进制文件本体。

### 1.4 3.4 多格式解析/OCR（解析层）
- `.docx`：`python-docx`（含嵌图 OCR 尝试）
- `.pptx`：`python-pptx`（含嵌图 OCR 尝试）
- `.pdf`：优先 MinerU，失败回退 PyMuPDF 文本，再回退 OCR
- 图片（`.png/.jpg/...`）：OCR（PaddleOCR 或 RapidOCR）
- `.doc`：专用链路（antiword -> catdoc -> soffice -> Word COM）

结论：OCR 只负责“把图像内容转成文本块参与分块/检索”，不是保存整张图片内容到索引。

## 2. 运行前准备

### 2.1 目录与 Python
- 仓库目录：`H:\Desktop\计设\pc_orchestrator_core`
- Python：`.\.venv\Scripts\python.exe`
- WebSocket 地址：`ws://127.0.0.1:3210/ws/orchestrator`

### 2.2 `.doc` 解析依赖（至少一个）
- `antiword`
- `catdoc`
- `LibreOffice/soffice`（推荐）
- `Word COM`（Windows + 本机 Office）

推荐配置 `soffice`：
```powershell
$env:ORCHESTRATOR_DOC_SOFFICE_BINARY="C:\Program Files\LibreOffice\program\soffice.exe"
```

### 2.3 Embedding 与 RAG 常用环境变量
```powershell
$env:ORCHESTRATOR_EMBEDDING_API_BASE="你的兼容网关URL"
$env:ORCHESTRATOR_EMBEDDING_API_KEY="你的Key"
$env:ORCHESTRATOR_EMBEDDING_MODEL="text-embedding-3-large"

$env:ORCHESTRATOR_RAG_LLM_ENABLED="1"
$env:ORCHESTRATOR_RAG_MULTI_QUERY="1"
$env:ORCHESTRATOR_RAG_HYDE="1"
$env:ORCHESTRATOR_RAG_RERANK="1"
$env:ORCHESTRATOR_RAG_ANSWER_ENABLED="1"
```

## 3. 后端启动命令（从零开始）

### 3.1 联调优先（允许 fallback，不阻塞上传）
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

### 3.2 严格模式（生产校验，Embedding 不可用即失败）
```powershell
cd H:\Desktop\计设\pc_orchestrator_core

$env:ORCHESTRATOR_DOC_SOFFICE_BINARY="C:\Program Files\LibreOffice\program\soffice.exe"
$env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED="0"

.\scripts\start_backend_checked.ps1 `
  -ServerHost 127.0.0.1 `
  -Port 3210 `
  -EmbeddingModel text-embedding-3-large
```

## 4. WebSocket 请求模板

统一请求格式：
```json
{
  "type": "req",
  "id": "request-id",
  "method": "orchestrator.xxx",
  "params": {}
}
```

统一事件响应格式：
```json
{
  "type": "event",
  "event": "orchestrator.xxx",
  "taskId": null,
  "nodeId": null,
  "sessionId": null,
  "payload": {}
}
```

## 5. 端到端操作步骤（含输入和期望输出）

下面示例默认你已有 `courseId`。如果没有先执行 5.1。

### 5.1 创建课程

输入：
```json
{
  "type": "req",
  "id": "course-create-001",
  "method": "orchestrator.knowledge.course.create",
  "params": {
    "courseName": "软件设计模式",
    "courseDescription": "知识库联调课程"
  }
}
```

期望输出：
- `event = orchestrator.knowledge.course.create`
- `payload.courseId` 非空

### 5.2 上传文件入库（示例：`.doc`）

输入：
```json
{
  "type": "req",
  "id": "file-ingest-doc-001",
  "method": "orchestrator.knowledge.file.ingest",
  "params": {
    "courseId": "替换为你的courseId",
    "filePath": "H:\\Desktop\\计设\\samples\\docDemo.doc",
    "fileName": "docDemo.doc",
    "chunkSize": 900
  }
}
```

期望输出：
- `event = orchestrator.knowledge.file.ingest`
- `payload.status = "success"`
- `payload.chunkCount > 0`
- `payload.fileId` 非空

说明：
- “上传时触发 embedding”是正常逻辑，因为 ingest 内部包含 `parse -> chunk -> embed -> store -> reindex` 全流程。

### 5.3 验证是否真的存储成功（你最关心的点）

第一步，查看文件记录：
```json
{
  "type": "req",
  "id": "file-list-001",
  "method": "orchestrator.knowledge.file.list",
  "params": {
    "courseId": "替换为你的courseId",
    "limit": 200
  }
}
```

期望输出：
- `payload.items[]` 中存在新 `fileId`
- `parseStatus = "success"`
- `storedPath` 指向 `data/knowledge_bases/<courseId>/raw/...`

第二步，查看分块结果：
```json
{
  "type": "req",
  "id": "chunk-list-001",
  "method": "orchestrator.knowledge.chunk.list",
  "params": {
    "courseId": "替换为你的courseId",
    "limit": 100
  }
}
```

期望输出：
- `payload.items[]` 非空
- 至少出现刚上传文件对应的 chunk
- `metadata.parser` 对应解析器生效（例如 `python-docx`、`python-pptx`、`pymupdf`、`rapidocr`、`soffice-txt`）

### 5.4 RAG 查询

输入：
```json
{
  "type": "req",
  "id": "rag-query-001",
  "method": "orchestrator.knowledge.rag.query",
  "params": {
    "courseId": "替换为你的courseId",
    "text": "Observer pattern 核心思想是什么？",
    "limit": 8
  }
}
```

期望输出：
- `payload.items[]` 非空
- `payload.answer` 非空（若 LLM 不可用会走 extractive fallback，也应有答案）
- `payload.debug.multiQueries` 非空
- `payload.debug.hydeSource` 存在
- `payload.debug.rerankMode` 为 `local` 或 `api`

如果 `hyde` 为空，重点看：
- `payload.debug.hydeSource`
- `payload.debug.hydeError`

### 5.5 课程重嵌入（`course.reembed`）

输入：
```json
{
  "type": "req",
  "id": "course-reembed-001",
  "method": "orchestrator.knowledge.course.reembed",
  "params": {
    "courseId": "替换为你的courseId",
    "batchSize": 32
  }
}
```

期望输出：
- `payload.chunkCount` = 课程当前 chunk 总数
- `payload.updatedCount` = 实际更新 embedding 数
- `payload.dimensions` > 0
- `payload.fallbackUsed` 反映是否回退 hash
- `payload.fallbackReason` 可用于定位 API/model 问题

重嵌入逻辑：
- 读取该课程全部 chunk 文本
- 按 `batchSize` 批量请求 embedding
- 回写 `knowledge_chunks.embedding_json`
- 最后自动重建课程向量索引

### 5.6 课程索引重建与 Memory 索引重建

课程索引重建：
```json
{
  "type": "req",
  "id": "course-reindex-001",
  "method": "orchestrator.knowledge.course.reindex",
  "params": {
    "courseId": "替换为你的courseId"
  }
}
```

期望输出：
- `payload.indexBackend`（如 `json/faiss/chroma/none`）
- `payload.chunkCount` 正常
- `payload.dimensions` 正常

Memory 索引重建：
```json
{
  "type": "req",
  "id": "memory-reindex-001",
  "method": "orchestrator.memory.reindex",
  "params": {}
}
```

期望输出：
- `payload.indexBackend`
- `payload.documentCount`
- `payload.dimensions`

说明：
- `course.reindex` 针对知识库 chunk 向量索引。
- `memory.reindex` 针对会话记忆摘要/事实向量索引。
- 两者作用域不同，互不替代。

### 5.7 删除旧入库记录（例如错误 `.doc`）

先查 `fileId`（5.3 的 `file.list`），再删：
```json
{
  "type": "req",
  "id": "file-delete-001",
  "method": "orchestrator.knowledge.file.delete",
  "params": {
    "courseId": "替换为你的courseId",
    "target": "替换为要删除的fileId"
  }
}
```

期望输出：
- `payload.deleted = true`
- `payload.chunkCount >= 0`
- `payload.removedRawFile = true/false`

## 6. 测试清单（可逐条执行）

### T01 启动健康检查
- 操作：执行第 3 章启动命令。
- 期望：控制台出现 `Orchestrator listening on ws://127.0.0.1:3210/ws/orchestrator`。

### T02 `.docx` 入库
- 输入：正常中文/英文文本 `docx`。
- 操作：`orchestrator.knowledge.file.ingest`。
- 期望：`status=success`，`chunkCount>0`，chunk 的 `metadata.parser=python-docx`。

### T03 `.pptx` 入库
- 输入：有文本的 `pptx`。
- 期望：`status=success`，chunk 的 `metadata.parser=python-pptx`。

### T04 `.pdf` 入库
- 输入：可提取文本的 `pdf`。
- 期望：`status=success`，chunk 的 `metadata.parser` 为 `mineru` 或 `pymupdf` 或 `pymupdf+paddleocr`。

### T05 `.png` 入库（OCR）
- 输入：图片里包含可识别文本。
- 期望：`status=success`，chunk 的 `sourceSection=ocr`，`metadata.parser` 为 `paddleocr` 或 `rapidocr`。

### T06 `.doc` 入库
- 输入：老 Word 格式 `.doc`。
- 期望：`status=success`，chunk 文本可读，不出现二进制乱码块。
- 若失败：错误中会给出缺失后端详情（antiword/catdoc/soffice/Word COM）。

### T07 RAG 查询
- 输入：对已入库内容提问。
- 期望：`items` 命中相关 chunk，`answer` 非空，`debug` 字段包含 `multiQueries/hydeSource/rerankMode`。

### T08 课程重嵌入
- 操作：`orchestrator.knowledge.course.reembed`。
- 期望：`updatedCount = chunkCount`（通常），`dimensions>0`，并检查 `fallbackUsed` 是否符合预期。

### T09 删除错误文件并复查
- 操作：删掉某 `fileId`，再执行同主题查询。
- 期望：被删文件对应 chunk 不再参与检索。

### T10 索引重建
- 操作：执行 `course.reindex` 与 `memory.reindex`。
- 期望：两者均返回非异常，计数和维度合理。

## 7. 自动化/单元测试命令

核心回归（推荐每次改动后执行）：
```powershell
cd H:\Desktop\计设\pc_orchestrator_core
.\.venv\Scripts\python.exe -m unittest tests.test_knowledge_parsers tests.test_rag_service
```

解析器专项：
```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_knowledge_parsers
```

RAG 专项：
```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rag_service
```

通过标准：
- 输出含 `Ran ... tests`
- 最终状态 `OK`

## 8. 常见问题定位

### 8.1 `PaddleOCR is required...` 或 OCR 引擎不可用
- 含义：图片 OCR 依赖不可用。
- 处理：安装 PaddleOCR 或 RapidOCR，或检查 `ORCHESTRATOR_OCR_ENGINE` 配置。

### 8.2 `DOC parsing failed ... binary not found`
- 含义：`.doc` 后端未安装或路径未配置。
- 处理：优先配置 `ORCHESTRATOR_DOC_SOFFICE_BINARY` 指向真实 `soffice.exe`。

### 8.3 `soffice returned empty text`
- 含义：`soffice` 转换成功但文本提取为空。
- 常见原因：源文件本身无可提取文本，或内容实际是扫描件。
- 处理：先手工打开文档确认有文本；扫描件建议转图片/PDF 后走 OCR。

### 8.4 `Embedding provider unavailable` / `model_not_found`
- 含义：embedding API 调用失败或模型不可用。
- 处理：联调阶段可开 `ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED=1`；生产校验请关闭 fallback 并修正模型/API。

### 8.5 上传成功但查询无回答
- 检查 `payload.answer`、`payload.debug.answerSource`、`payload.debug.answerError`。
- 检查 `payload.items` 是否为空；若为空先确认 `chunk.list` 是否已有有效文本块。

## 9. 快速命令备忘

后端启动（联调）：
```powershell
cd H:\Desktop\计设\pc_orchestrator_core
$env:ORCHESTRATOR_DOC_SOFFICE_BINARY="C:\Program Files\LibreOffice\program\soffice.exe"
$env:ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND="json"
$env:ORCHESTRATOR_MEMORY_INDEX_BACKEND="json"
$env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED="1"
.\.venv\Scripts\python.exe -m backend.main --host 127.0.0.1 --port 3210
```

嵌入可用性预检查：
```powershell
.\.venv\Scripts\python.exe -m backend.dev.check_embedding_endpoint --check-chat --retries 3 --timeout 45
```

## 10. 前端联调步骤（知识库页 + 记忆页 + LangSmith）

前提：
- 后端已启动（第 3 章）。
- 前端已启动：`cd H:\Desktop\计设\pc_orchestrator_core\frontend && npm run dev`

### 10.1 设置页配置 LangSmith
- 进入顶部 `设置` 页签。
- 在 `LangSmith` 区域填写：
  - `启用 LangSmith Tracing`（开关）
  - `LangSmith Project`
  - `LangSmith API Key`
  - `LangSmith API URL`（可选）
- 点击 `保存运行时设置`。

期望输出：
- 顶部提示 `设置已保存。`
- 后端收到 `orchestrator.config.set`，并在 `orchestrator.config.get/set` 里返回 `payload.langsmith` 字段。

### 10.2 知识库页
- 进入顶部 `知识库/RAG` 页签。
- 创建课程 -> 选择课程 -> 上传文件入库。
- 点击 `刷新文件/分块/任务`。
- 在 `RAG 查询` 输入问题并执行查询。

期望输出：
- 文件列表出现新文件，状态 `success`。
- 分块区出现可读文本，且 `parser` 与文件类型对应。
- `答案` 区域非空（或显示“仅返回检索片段”）。
- `HyDE` 与 `answerSource/hydeSource` 可用于定位是否走了 LLM。

### 10.3 记忆页
- 进入顶部 `记忆` 页签。
- 在 `Search query` 输入问题并点击 `Search`。
- 执行 `Cleanup Memory` 与 `Reindex Memory`。

期望输出：
- Search 返回 `Results` 列表（可能为空，但事件需成功）。
- Cleanup/Reindex 成功提示。
- 若失败，错误提示中包含后端返回的具体错误信息。

## 11. 一键 Smoke 脚本（推荐）

新增脚本：`scripts/e2e_kb_rag_memory.py`

作用：
- `config.get`（可选 `config.set` 写 LangSmith）
- 课程创建/列表
- 文件入库
- 文件/分块列表校验
- RAG 查询
- 课程重嵌入
- 课程重建索引
- Memory 重建索引与检索

示例命令（包含入库与 LangSmith 配置）：
```powershell
cd H:\Desktop\计设\pc_orchestrator_core

.\.venv\Scripts\python.exe .\scripts\e2e_kb_rag_memory.py `
  --ws-url ws://127.0.0.1:3210/ws/orchestrator `
  --course-name "smoke-course-001" `
  --course-description "smoke test" `
  --file-path "H:\Desktop\计设\samples\docxDemo.docx" `
  --file-path "H:\Desktop\计设\samples\pngDemo.png" `
  --query "Observer pattern 核心思想是什么？" `
  --set-langsmith `
  --langsmith-enabled 1 `
  --langsmith-project "pc-orchestrator-core"
```

期望输出：
- 控制台打印若干 `[ok] event=...`。
- 结束时打印 `[final-summary]` JSON，含：
  - `courseId`
  - `fileCount/chunkCount`
  - `ragHitCount/ragAnswer`
  - `reembed.courseReindex.memoryReindex` 统计
