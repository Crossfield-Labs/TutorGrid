# Knowledge / RAG / Memory Runtime Config

This document lists environment variables added for the current backend implementation.

## Embedding

- `ORCHESTRATOR_EMBEDDING_PROVIDER`: `openai_compat` (default) or `hash`
- `ORCHESTRATOR_EMBEDDING_MODEL`: embedding model name (default: `text-embedding-3-large`)
- `ORCHESTRATOR_EMBEDDING_API_BASE`: OpenAI-compatible API base URL
- `ORCHESTRATOR_EMBEDDING_API_KEY`: API key
- `ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED`: `true/false` (default: `true`)
  - `true`: if embedding API fails, fallback to local hash embedding (96 dims).
  - `false`: fail fast instead of silently falling back (recommended for production validation).

## Embedding Preflight Check

- Script: `python -m backend.dev.check_embedding_endpoint`
- Purpose: verify `/embeddings` is actually usable before starting backend.
- Example:

```powershell
.\.venv\Scripts\python.exe -m backend.dev.check_embedding_endpoint --check-chat --retries 3 --timeout 45
```

- Exit code:
  - `0`: embedding endpoint is usable.
  - `2`: failed (network/model/auth/response mismatch).

## One-Click Startup (Checked)

Use the startup script to enforce preflight check first:

```powershell
.\scripts\start_backend_checked.ps1 -ServerHost 127.0.0.1 -Port 3210 -EmbeddingModel text-embedding-3-large
```

Notes:
- Default behavior blocks startup if embedding check fails.
- Add `-AllowHashFallback` if you intentionally allow hash fallback.
- Add `-SkipChatCheck` if you only want embedding verification.

## Vector Retrieval Backend

- `ORCHESTRATOR_VECTOR_STORE_BACKEND`: `auto` (default), `faiss`, `chroma`, `python`
  - `auto`: try `faiss`, then `chroma`, then Python fallback
  - `python`: pure in-memory brute-force ranking fallback

## Knowledge Vector Index

- `ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND`: `auto` (default), `faiss`, `chroma`, `json`, `none`
  - `auto`: try persistent `faiss`, then persistent `chroma`, then local `json`.
  - `json`: lightweight fallback for environments without FAISS/Chroma.
  - Knowledge index is rebuilt on file ingest/delete and course re-embed.

## Memory Vector Index

- `ORCHESTRATOR_MEMORY_INDEX_BACKEND`: `auto` (default), `faiss`, `chroma`, `json`, `none`
  - `auto`: try persistent `faiss`, then persistent `chroma`, then local `json`.
  - Memory index is rebuilt after `memory.compact` and can be manually rebuilt via `memory.reindex`.

## PDF Parsing Strategy

- `ORCHESTRATOR_PDF_PARSE_STRATEGY`: `auto` (default), `mineru`, `pymupdf`, `ocr`
- `ORCHESTRATOR_MINERU_ENABLED`: `true/false` (default: `true`)
- `ORCHESTRATOR_MINERU_BINARY`: MinerU CLI command (default: `mineru`)
- `ORCHESTRATOR_MINERU_BACKEND`: MinerU backend (default: `pipeline`)
- `ORCHESTRATOR_MINERU_TIMEOUT_SEC`: MinerU CLI timeout in seconds (default: `900`)
- `ORCHESTRATOR_PDF_OCR_FALLBACK`: `true/false` (default: `true`)
- `ORCHESTRATOR_PDF_OCR_DPI`: render DPI for PDF page OCR (default: `220`)

## DOC Parsing (Legacy .doc)

- `.doc` files are parsed with dedicated backends instead of plaintext fallback.
- Backend order: `antiword` -> `catdoc` -> `soffice/libreoffice` -> `Word COM (Windows)`.
- `ORCHESTRATOR_DOC_ANTIWORD_BINARY`: antiword command (default: `antiword`)
- `ORCHESTRATOR_DOC_CATDOC_BINARY`: catdoc command (default: `catdoc`)
- `ORCHESTRATOR_DOC_SOFFICE_BINARY`: soffice command (default: `soffice`)
- `ORCHESTRATOR_DOC_WORD_COM_ENABLED`: `true/false` (default: `true`, Windows only)

## OCR

- `ORCHESTRATOR_PADDLEOCR_LANG`: PaddleOCR language code (default: `ch`)
- Embedded images in `pptx` / `docx` are OCR-extracted in best-effort mode.
  - If PaddleOCR is unavailable or OCR fails for an image, text parsing still succeeds.

## RAG Optimization

- `ORCHESTRATOR_RAG_MULTI_QUERY`: enable/disable Multi-Query (default: `true`)
- `ORCHESTRATOR_RAG_MULTI_QUERY_COUNT`: number of query variants (default: `3`)
- `ORCHESTRATOR_RAG_HYDE`: enable/disable HyDE (default: `true`)
- `ORCHESTRATOR_RAG_HYDE_ATTEMPTS`: HyDE generation attempts (default: `2`)
- `ORCHESTRATOR_RAG_HYDE_QUERY_FALLBACK`: fallback to original query when HyDE fails (default: `true`)
- `ORCHESTRATOR_RAG_RERANK`: enable/disable rerank stage (default: `true`)
- `ORCHESTRATOR_RAG_ANSWER_ENABLED`: return synthesized `answer` in `rag.query` response (default: `true`)
- `ORCHESTRATOR_RAG_ANSWER_ATTEMPTS`: answer generation attempts (default: `2`)
- `ORCHESTRATOR_RAG_ANSWER_MAX_CHARS`: max answer length (default: `1200`)
- `ORCHESTRATOR_RAG_MAX_CANDIDATES`: max candidates before rerank (default: `60`)
- `ORCHESTRATOR_RAG_RRF_K`: RRF constant (default: `60`)
- `ORCHESTRATOR_RERANK_API_BASE`: external rerank endpoint base
- `ORCHESTRATOR_RERANK_API_KEY`: external rerank API key
- `ORCHESTRATOR_RERANK_MODEL`: external rerank model name

## LangSmith

- `ORCHESTRATOR_LANGSMITH_ENABLED`: `true/false`
- `LANGSMITH_TRACING`: fallback switch if the variable above is unset
- `ORCHESTRATOR_LANGSMITH_PROJECT`: custom project name
- `LANGSMITH_PROJECT`: fallback project name

Current tracing coverage:
- knowledge ingest pipeline
- rag query pipeline
- memory compaction and memory search
