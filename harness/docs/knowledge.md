# Knowledge / RAG 模块

权威说明优先级：
- 运行与联调细节以 `docs/知识库_RAG_记忆_操作手册.md` 为准
- 环境变量与部署参数以 `docs/kb-rag-memory-config.md` 为准
- 评测、benchmark、workflow 脚本以 `docs/rag-eval-and-ingest-benchmark.md` 为准
- 本文件只保留 harness 视角下的模块边界、入口和同步要求

主要代码：
- `backend/knowledge/`
- `backend/rag/`
- `backend/vector/`
- `backend/learning_profile/`
- `backend/observability/langsmith.py`
- `backend/server/app.py`

职责：
- 维护课程级知识库、文件记录、解析作业和知识块存储
- 提供多格式文档解析、分块、embedding、向量索引与重建
- 提供课程内 `RAG query` 检索、融合排序、可选答案生成
- 维护学习画像的 `L1 / L2 / L4` 数据层与对外服务
- 为 knowledge ingest、RAG query、memory compaction/search 提供 LangSmith tracing

主要模块边界：
- `backend/knowledge/`
  - 负责课程、文件、job、chunk 的落库和文件摄取
  - `KnowledgeBaseService` 会把原始文件复制到 `data/knowledge_bases/<course_id>/raw/`
  - chunk 写入 `knowledge_chunks`，并触发课程级索引重建
- `backend/rag/`
  - 负责查询改写、多路召回、HyDE、融合排序、rerank 和答案拼装
  - 不直接管理文件摄取和 chunk 生命周期，只消费 knowledge 层已落好的 chunks / index
- `backend/vector/`
  - 提供 knowledge / memory 两套持久化索引
  - 后端选择支持 `faiss`、`chroma`、`json` fallback
- `backend/learning_profile/`
  - 负责学习画像持久化与查询
  - 当前稳定层级是 `L1` 偏好、`L2` 课程上下文、`L4` 知识点掌握度
- `backend/observability/langsmith.py`
  - 提供 best-effort tracing，不应该阻断主流程

当前对外协议入口：
- `orchestrator.profile.get`
- `orchestrator.profile.l1.set`
- `orchestrator.profile.l2.list`
- `orchestrator.profile.l2.upsert`
- `orchestrator.profile.l4.list`
- `orchestrator.profile.l4.upsert`
- `orchestrator.knowledge.course.create`
- `orchestrator.knowledge.course.list`
- `orchestrator.knowledge.course.delete`
- `orchestrator.knowledge.course.reembed`
- `orchestrator.knowledge.course.reindex`
- `orchestrator.knowledge.file.ingest`
- `orchestrator.knowledge.file.list`
- `orchestrator.knowledge.file.delete`
- `orchestrator.knowledge.chunk.list`
- `orchestrator.knowledge.job.list`
- `orchestrator.knowledge.job.get`
- `orchestrator.knowledge.rag.query`

关键点：
- knowledge / learning profile / memory 当前都直接使用各自独立的 `sqlite3` store，不依赖统一 ORM
- knowledge ingest 是同步摄取链路：staging -> parse -> chunk -> embed -> store -> reindex
- 课程级向量索引落在 `data/knowledge_bases/<course_id>/index/`
- `RAG` 同时走 dense + lexical，再做融合；rerank 优先外部 API，否则退回本地逻辑
- 多格式解析、OCR、fallback、典型请求样例不要在这里重复展开，直接看上面的权威文档

修改时注意：
- 新增文件解析后端、OCR 策略、联调步骤时，优先更新 `docs/知识库_RAG_记忆_操作手册.md`
- 环境变量、fallback 规则、启动脚本变化时，优先更新 `docs/kb-rag-memory-config.md`
- 新增评测脚本、dataset 格式或 workflow 产物时，优先更新 `docs/rag-eval-and-ingest-benchmark.md`
- 新增 knowledge / profile / rag 协议方法时，要同步更新 `harness/docs/server.md`
- 如果课程索引目录结构、落盘位置或 fallback 规则变化，要同步更新本文件
- 如果学习画像层级或字段定义变化，要同步更新本文件和 `docs/persistence.md`
