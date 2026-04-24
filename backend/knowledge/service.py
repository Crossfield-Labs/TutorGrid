from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from backend.config import load_config
from backend.knowledge.chunking import ChunkBuilder
from backend.knowledge.parsers import ParserRegistry
from backend.knowledge.store import SQLiteKnowledgeStore
from backend.memory.embedding import HashedTokenEmbedder, OpenAICompatEmbedder, TextEmbedder
from backend.observability import get_langsmith_tracer
from backend.vector import KnowledgeVectorIndex


class KnowledgeBaseService:
    def __init__(
        self,
        *,
        store: SQLiteKnowledgeStore | None = None,
        root: Path | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "data" / "knowledge_bases"
        self.root.mkdir(parents=True, exist_ok=True)
        db_path = Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        self.store = store or SQLiteKnowledgeStore(db_path)
        self.parsers = ParserRegistry()
        self.fallback_embedder = HashedTokenEmbedder()
        self.embedding_fallback_enabled = self._bool_env("ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED", True)
        self.last_embedding_error = ""
        self.last_embedding_fallback_used = False
        self.embedding_provider_name = ""
        self.embedding_model_name = ""
        if embedder is not None:
            self.embedder = embedder
            self.embedding_provider_name = self._describe_embedder(embedder)
        else:
            self.embedder = self._build_default_embedder()
        if not self.embedding_provider_name:
            self.embedding_provider_name = self._describe_embedder(self.embedder)
        index_backend = os.environ.get(
            "ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND",
            os.environ.get("ORCHESTRATOR_VECTOR_STORE_BACKEND", "auto"),
        ).strip().lower()
        self.vector_index = KnowledgeVectorIndex(root=self.root, backend=index_backend or "auto")
        self.tracer = get_langsmith_tracer()

    def create_course(self, *, name: str, description: str = "") -> dict[str, Any]:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Course name cannot be empty.")
        return self.store.create_course(name=normalized_name, description=description.strip())

    def list_courses(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_courses(limit=limit)

    def delete_course(self, *, course_id: str) -> dict[str, Any]:
        normalized_course = course_id.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        course = self.store.get_course(normalized_course)
        if course is None:
            raise ValueError("Course not found.")
        run_id = self.tracer.start_run(
            name="knowledge.delete_course",
            run_type="chain",
            inputs={"courseId": normalized_course},
            metadata={"module": "knowledge"},
            tags=["knowledge", "delete"],
        )
        try:
            deleted = self.store.delete_course(course_id=normalized_course)
            self.vector_index.delete_course(course_id=normalized_course)
            course_dir = self.root / normalized_course
            removed_raw_files = 0
            if course_dir.exists():
                try:
                    for path in course_dir.rglob("*"):
                        if path.is_file():
                            removed_raw_files += 1
                    shutil.rmtree(course_dir, ignore_errors=True)
                except Exception:
                    pass
            payload = {
                "courseId": normalized_course,
                "deleted": bool(deleted.get("deleted")),
                "fileCount": int(deleted.get("fileCount") or 0),
                "chunkCount": int(deleted.get("chunkCount") or 0),
                "jobCount": int(deleted.get("jobCount") or 0),
                "removedRawFiles": removed_raw_files,
            }
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "knowledge"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"courseId": normalized_course},
                error=(str(exc).strip() or "delete course failed")[:1200],
                metadata={"module": "knowledge"},
                tags=["error"],
            )
            raise

    def ingest_file(
        self,
        *,
        course_id: str,
        file_path: str,
        file_name: str = "",
        chunk_size: int = 900,
    ) -> dict[str, Any]:
        course = self.store.get_course(course_id.strip())
        if course is None:
            raise ValueError("Course not found.")
        source_path = Path(file_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {source_path}")

        raw_dir = self.root / course_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        file_ext = source_path.suffix.lower()
        staged_file_name = f"{Path(source_path).stem}_{source_path.stat().st_size}{file_ext}"
        staged_path = raw_dir / staged_file_name
        shutil.copy2(source_path, staged_path)

        display_name = file_name.strip() or source_path.name
        file_record = self.store.create_file_record(
            course_id=course_id,
            original_name=display_name,
            stored_path=str(staged_path),
            file_ext=file_ext,
            source_type="local",
        )
        job_record = self.store.create_job(
            course_id=course_id,
            file_id=str(file_record["fileId"]),
            status="processing",
            progress=0.1,
            message="File staged. Starting parser.",
        )
        file_id = str(file_record["fileId"])
        job_id = str(job_record["jobId"])
        run_id = self.tracer.start_run(
            name="knowledge.ingest_file",
            run_type="chain",
            inputs={
                "courseId": course_id,
                "filePath": str(source_path),
                "fileName": display_name,
                "chunkSize": max(200, int(chunk_size)),
            },
            metadata={"module": "knowledge"},
            tags=["knowledge", "ingestion"],
        )

        try:
            parse_run_id = self.tracer.start_run(
                name="knowledge.parse",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"filePath": str(staged_path), "ext": file_ext},
                metadata={"stage": "parse"},
                tags=["knowledge", "parse"],
            )
            try:
                parsed = self.parsers.parse_document(staged_path)
            except Exception as exc:
                self.tracer.end_run(
                    parse_run_id,
                    error=(str(exc).strip() or "parse stage failed")[:1200],
                    metadata={"stage": "parse"},
                    tags=["error"],
                )
                raise
            self.tracer.end_run(
                parse_run_id,
                outputs={"blockCount": len(parsed.blocks), "title": parsed.title},
                metadata={"stage": "parse"},
            )
            self.store.update_job(job_id=job_id, status="processing", progress=0.55, message="Parsing completed.")

            chunk_run_id = self.tracer.start_run(
                name="knowledge.chunk",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"blockCount": len(parsed.blocks), "maxChars": max(200, int(chunk_size))},
                metadata={"stage": "chunk"},
                tags=["knowledge", "chunk"],
            )
            try:
                chunk_builder = ChunkBuilder(max_chars=max(200, int(chunk_size)))
                chunks = chunk_builder.chunk_document(parsed)
                if not chunks:
                    raise RuntimeError("Parser returned no usable text chunks.")
            except Exception as exc:
                self.tracer.end_run(
                    chunk_run_id,
                    error=(str(exc).strip() or "chunk stage failed")[:1200],
                    metadata={"stage": "chunk"},
                    tags=["error"],
                )
                raise
            self.tracer.end_run(
                chunk_run_id,
                outputs={"chunkCount": len(chunks)},
                metadata={"stage": "chunk"},
            )

            embed_run_id = self.tracer.start_run(
                name="knowledge.embed",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"chunkCount": len(chunks)},
                metadata={"stage": "embed"},
                tags=["knowledge", "embed"],
            )
            embed_fallback_used = False
            embed_error = ""
            try:
                vectors = self._embed_texts([chunk.content for chunk in chunks])
                embed_fallback_used = self.last_embedding_fallback_used
                embed_error = self.last_embedding_error
                for chunk, embedding in zip(chunks, vectors, strict=False):
                    chunk.embedding = embedding
            except Exception as exc:
                self.tracer.end_run(
                    embed_run_id,
                    error=(str(exc).strip() or "embedding stage failed")[:1200],
                    metadata={"stage": "embed"},
                    tags=["error"],
                )
                raise
            self.tracer.end_run(
                embed_run_id,
                outputs={
                    "vectorCount": len(vectors),
                    "dimensions": len(vectors[0]) if vectors else 0,
                    "provider": self.embedding_provider_name,
                    "model": self.embedding_model_name,
                    "fallbackEnabled": self.embedding_fallback_enabled,
                    "fallbackUsed": embed_fallback_used,
                    "fallbackReason": embed_error[:240],
                },
                metadata={"stage": "embed"},
            )

            store_run_id = self.tracer.start_run(
                name="knowledge.store",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"chunkCount": len(chunks), "courseId": course_id},
                metadata={"stage": "store"},
                tags=["knowledge", "store"],
            )
            try:
                chunk_count = self.store.replace_file_chunks(course_id=course_id, file_id=file_id, chunks=chunks)
            except Exception as exc:
                self.tracer.end_run(
                    store_run_id,
                    error=(str(exc).strip() or "store stage failed")[:1200],
                    metadata={"stage": "store"},
                    tags=["error"],
                )
                raise
            self.tracer.end_run(
                store_run_id,
                outputs={"storedChunks": chunk_count},
                metadata={"stage": "store"},
            )
            self.store.update_file_status(file_id=file_id, status="success", parse_error="")
            self.store.update_job(
                job_id=job_id,
                status="success",
                progress=1.0,
                message=f"Ingestion completed with {chunk_count} chunks.",
            )
            index_state = self._rebuild_course_index(course_id=course_id)
            self.tracer.end_run(
                run_id,
                outputs={
                    "jobId": job_id,
                    "courseId": course_id,
                    "fileId": file_id,
                    "status": "success",
                    "chunkCount": chunk_count,
                    "indexBackend": index_state.get("backend", "none"),
                    "embeddingProvider": self.embedding_provider_name,
                    "embeddingModel": self.embedding_model_name,
                    "fallbackEnabled": self.embedding_fallback_enabled,
                    "fallbackUsed": embed_fallback_used,
                    "fallbackReason": embed_error[:240],
                },
                metadata={"module": "knowledge"},
            )
            return {
                "jobId": job_id,
                "courseId": course_id,
                "fileId": file_id,
                "status": "success",
                "chunkCount": chunk_count,
                "indexBackend": index_state.get("backend", "none"),
                "embeddingProvider": self.embedding_provider_name,
                "embeddingModel": self.embedding_model_name,
                "fallbackEnabled": self.embedding_fallback_enabled,
                "fallbackUsed": embed_fallback_used,
                "fallbackReason": embed_error[:240],
            }
        except Exception as exc:
            error_text = str(exc).strip() or "Unknown parser failure."
            self.store.update_file_status(file_id=file_id, status="failed", parse_error=error_text[:1200])
            self.store.update_job(job_id=job_id, status="failed", progress=1.0, message=error_text[:1200])
            self.tracer.end_run(
                run_id,
                outputs={"jobId": job_id, "courseId": course_id, "fileId": file_id, "status": "failed"},
                error=error_text[:1200],
                metadata={"module": "knowledge"},
                tags=["error"],
            )
            return {
                "jobId": job_id,
                "courseId": course_id,
                "fileId": file_id,
                "status": "failed",
                "chunkCount": 0,
                "error": error_text,
            }

    def get_job(self, *, job_id: str) -> dict[str, Any] | None:
        return self.store.get_job(job_id.strip())

    def list_jobs(self, *, course_id: str, limit: int = 100) -> list[dict[str, Any]]:
        normalized_course = course_id.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if self.store.get_course(normalized_course) is None:
            raise ValueError("Course not found.")
        return self.store.list_jobs(course_id=normalized_course, limit=max(1, int(limit)))

    def list_files(self, *, course_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.store.list_files(course_id=course_id.strip(), limit=limit)

    def delete_file(self, *, course_id: str, file_id: str) -> dict[str, Any]:
        normalized_course = course_id.strip()
        normalized_file = file_id.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if not normalized_file:
            raise ValueError("fileId cannot be empty.")
        course = self.store.get_course(normalized_course)
        if course is None:
            raise ValueError("Course not found.")
        file_record = self.store.get_file(file_id=normalized_file)
        if file_record is None:
            raise ValueError("File not found.")
        if str(file_record.get("courseId") or "") != normalized_course:
            raise ValueError("The file does not belong to the given course.")

        run_id = self.tracer.start_run(
            name="knowledge.delete_file",
            run_type="chain",
            inputs={"courseId": normalized_course, "fileId": normalized_file},
            metadata={"module": "knowledge"},
            tags=["knowledge", "delete"],
        )
        try:
            deleted = self.store.delete_file(file_id=normalized_file)
            index_state = self._rebuild_course_index(course_id=normalized_course)
            stored_path = str(deleted.get("storedPath") or "").strip()
            removed_raw_file = False
            if stored_path:
                path = Path(stored_path).expanduser()
                if path.exists() and path.is_file():
                    try:
                        course_root = (self.root / normalized_course).resolve()
                        resolved = path.resolve()
                        if str(resolved).startswith(str(course_root)):
                            path.unlink(missing_ok=True)
                            removed_raw_file = True
                    except Exception:
                        pass
            payload = {
                "courseId": normalized_course,
                "fileId": normalized_file,
                "deleted": bool(deleted.get("deleted")),
                "chunkCount": int(deleted.get("chunkCount") or 0),
                "jobCount": int(deleted.get("jobCount") or 0),
                "removedRawFile": removed_raw_file,
                "indexBackend": str(index_state.get("backend") or "none"),
            }
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "knowledge"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"courseId": normalized_course, "fileId": normalized_file},
                error=(str(exc).strip() or "delete file failed")[:1200],
                metadata={"module": "knowledge"},
                tags=["error"],
            )
            raise

    def list_chunks(self, *, course_id: str, limit: int = 100, query: str = "") -> list[dict[str, Any]]:
        return self.store.list_chunks(course_id=course_id.strip(), limit=limit, query=query)

    def list_chunks_for_retrieval(self, *, course_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        return self.store.list_chunks_for_retrieval(course_id=course_id.strip(), limit=limit)

    def reindex_course(self, *, course_id: str) -> dict[str, Any]:
        normalized_course = course_id.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if self.store.get_course(normalized_course) is None:
            raise ValueError("Course not found.")
        state = self._rebuild_course_index(course_id=normalized_course)
        return {
            "courseId": normalized_course,
            "indexBackend": str(state.get("backend") or "none"),
            "chunkCount": int(state.get("chunkCount") or 0),
            "dimensions": int(state.get("dimension") or 0),
        }

    def search_chunk_scores(self, *, course_id: str, queries: list[str], limit: int = 256) -> dict[str, float]:
        normalized_course = course_id.strip()
        if not normalized_course:
            return {}
        normalized_queries = [str(item or "").strip() for item in queries if str(item or "").strip()]
        if not normalized_queries:
            return {}
        query_vectors = self._embed_texts(normalized_queries)
        if not query_vectors:
            return {}
        safe_limit = max(1, int(limit))
        scores = self.vector_index.search(course_id=normalized_course, query_vectors=query_vectors, limit=safe_limit)
        if scores:
            return scores
        # Lazy backfill for old data that was ingested before index maintenance was added.
        rebuild = self._rebuild_course_index(course_id=normalized_course)
        if str(rebuild.get("backend") or "none") == "none":
            return {}
        return self.vector_index.search(course_id=normalized_course, query_vectors=query_vectors, limit=safe_limit)

    def reembed_course(self, *, course_id: str, batch_size: int = 64) -> dict[str, Any]:
        normalized_course = course_id.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if self.store.get_course(normalized_course) is None:
            raise ValueError("Course not found.")
        chunk_rows = self.store.list_chunk_texts(course_id=normalized_course)
        if not chunk_rows:
            return {
                "courseId": normalized_course,
                "chunkCount": 0,
                "updatedCount": 0,
                "batchSize": max(1, int(batch_size)),
                "dimensions": 0,
            }

        safe_batch_size = max(1, int(batch_size))
        run_id = self.tracer.start_run(
            name="knowledge.reembed_course",
            run_type="chain",
            inputs={"courseId": normalized_course, "chunkCount": len(chunk_rows), "batchSize": safe_batch_size},
            metadata={"module": "knowledge"},
            tags=["knowledge", "reembed"],
        )
        try:
            updated = 0
            dimensions = 0
            fallback_batch_count = 0
            fallback_reasons: list[str] = []
            for start in range(0, len(chunk_rows), safe_batch_size):
                batch = chunk_rows[start : start + safe_batch_size]
                texts = [str(item["content"]) for item in batch]
                vectors = self._embed_texts(texts)
                if self.last_embedding_fallback_used:
                    fallback_batch_count += 1
                    reason = self.last_embedding_error[:240]
                    if reason and reason not in fallback_reasons:
                        fallback_reasons.append(reason)
                pairs: list[tuple[str, list[float]]] = []
                for item, vector in zip(batch, vectors, strict=False):
                    chunk_id = str(item["chunkId"])
                    pairs.append((chunk_id, vector))
                    if vector and dimensions <= 0:
                        dimensions = len(vector)
                updated += self.store.update_chunk_embeddings(embeddings=pairs)
            index_state = self._rebuild_course_index(course_id=normalized_course)
            payload = {
                "courseId": normalized_course,
                "chunkCount": len(chunk_rows),
                "updatedCount": updated,
                "batchSize": safe_batch_size,
                "dimensions": dimensions,
                "indexBackend": str(index_state.get("backend") or "none"),
                "embeddingProvider": self.embedding_provider_name,
                "embeddingModel": self.embedding_model_name,
                "fallbackEnabled": self.embedding_fallback_enabled,
                "fallbackUsed": fallback_batch_count > 0,
                "fallbackBatchCount": fallback_batch_count,
                "fallbackReason": " | ".join(fallback_reasons)[:800],
            }
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "knowledge"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"courseId": normalized_course},
                error=(str(exc).strip() or "reembed course failed")[:1200],
                metadata={"module": "knowledge"},
                tags=["error"],
            )
            raise

    def embed_text(self, text: str) -> list[float]:
        vectors = self._embed_texts([text])
        return vectors[0] if vectors else []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embed_texts(texts)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self.last_embedding_error = ""
        self.last_embedding_fallback_used = False
        try:
            vectors = self.embedder.embed_texts(texts)
            if vectors and len(vectors) == len(texts):
                return vectors
            actual = len(vectors) if isinstance(vectors, list) else 0
            self.last_embedding_error = (
                f"Embedding provider returned {actual} vectors for {len(texts)} inputs."
            )
        except Exception as exc:
            self.last_embedding_error = str(exc).strip() or "embedding provider request failed"
        if not self.embedding_fallback_enabled:
            message = self.last_embedding_error or "embedding provider unavailable"
            raise RuntimeError(f"Embedding provider unavailable: {message}")
        self.last_embedding_fallback_used = True
        return self.fallback_embedder.embed_texts(texts)

    def _build_default_embedder(self) -> TextEmbedder:
        config = load_config()
        embedding_provider = os.environ.get("ORCHESTRATOR_EMBEDDING_PROVIDER", "openai_compat").strip().lower()
        embedding_model = os.environ.get("ORCHESTRATOR_EMBEDDING_MODEL", "text-embedding-3-large").strip()
        api_key = os.environ.get("ORCHESTRATOR_EMBEDDING_API_KEY", config.planner.api_key).strip()
        api_base = os.environ.get("ORCHESTRATOR_EMBEDDING_API_BASE", config.planner.api_base).strip()
        self.embedding_provider_name = embedding_provider or "openai_compat"
        self.embedding_model_name = embedding_model or "text-embedding-3-large"
        if embedding_provider in {"hash", "local_hash"}:
            self.embedding_provider_name = "hash"
            self.embedding_model_name = ""
            return HashedTokenEmbedder()
        if not api_key or not api_base:
            self.embedding_provider_name = "hash"
            self.embedding_model_name = ""
            return HashedTokenEmbedder()
        if embedding_provider in {"openai_compat", "openai-compatible", "openai"}:
            return OpenAICompatEmbedder(
                api_key=api_key,
                api_base=api_base,
                model=embedding_model or "text-embedding-3-large",
            )
        self.embedding_provider_name = "hash"
        self.embedding_model_name = ""
        return HashedTokenEmbedder()

    def _rebuild_course_index(self, *, course_id: str) -> dict[str, Any]:
        normalized_course = course_id.strip()
        if not normalized_course:
            return {"courseId": normalized_course, "backend": "none", "chunkCount": 0, "dimension": 0}
        chunks = self.store.list_chunks_for_retrieval(course_id=normalized_course, limit=200000)
        try:
            return self.vector_index.rebuild_course(course_id=normalized_course, chunks=chunks)
        except Exception:
            return {"courseId": normalized_course, "backend": "none", "chunkCount": 0, "dimension": 0}

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", ""}

    @staticmethod
    def _describe_embedder(embedder: TextEmbedder) -> str:
        if isinstance(embedder, OpenAICompatEmbedder):
            return "openai_compat"
        if isinstance(embedder, HashedTokenEmbedder):
            return "hash"
        return type(embedder).__name__
