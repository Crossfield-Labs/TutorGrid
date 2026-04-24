from __future__ import annotations

import os
from pathlib import Path

from backend.config import load_config
from backend.memory.compression import SessionMemoryCompressor
from backend.memory.embedding import HashedTokenEmbedder, OpenAICompatEmbedder, TextEmbedder
from backend.memory.models import MemorySearchResult
from backend.memory.sqlite_store import SQLiteMemoryStore
from backend.observability import get_langsmith_tracer
from backend.vector import MemoryVectorIndex


class MemoryService:
    def __init__(
        self,
        *,
        store: SQLiteMemoryStore | None = None,
        embedder: TextEmbedder | None = None,
        compressor: SessionMemoryCompressor | None = None,
        path: Path | None = None,
    ) -> None:
        db_path = path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        self.store = store or SQLiteMemoryStore(db_path)
        self.fallback_embedder = HashedTokenEmbedder()
        self.embedder = embedder or self._build_default_embedder()
        self.compressor = compressor or SessionMemoryCompressor()
        index_backend = os.environ.get(
            "ORCHESTRATOR_MEMORY_INDEX_BACKEND",
            os.environ.get("ORCHESTRATOR_VECTOR_STORE_BACKEND", "auto"),
        ).strip().lower()
        self.vector_index = MemoryVectorIndex(root=db_path.parent / "memory_index", backend=index_backend or "auto")
        self.tracer = get_langsmith_tracer()

    def compact_session(
        self,
        *,
        session_id: str,
        task: str,
        goal: str,
        history_items: list[dict[str, object]],
    ) -> dict[str, object]:
        run_id = self.tracer.start_run(
            name="memory.compact_session",
            run_type="chain",
            inputs={
                "sessionId": session_id,
                "task": task,
                "goal": goal,
                "historyCount": len(history_items),
            },
            metadata={"module": "memory"},
            tags=["memory", "compact"],
        )
        try:
            compress_run_id = self.tracer.start_run(
                name="memory.compress",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"historyCount": len(history_items)},
                metadata={"stage": "compress"},
                tags=["memory", "compress"],
            )
            result = self.compressor.compress_session(
                session_id=session_id,
                task=task,
                goal=goal,
                history_items=history_items,
            )
            self.tracer.end_run(
                compress_run_id,
                outputs={
                    "summaryLength": len(result.compaction.summary),
                    "factCount": len(result.compaction.facts),
                    "documentCount": len(result.documents),
                },
                metadata={"stage": "compress"},
            )

            embed_run_id = self.tracer.start_run(
                name="memory.embed",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"documentCount": len(result.documents)},
                metadata={"stage": "embed"},
                tags=["memory", "embed"],
            )
            payloads = [f"{document.title}\n{document.content}" for document in result.documents]
            vectors = self._embed_texts(payloads)
            for document, embedding in zip(result.documents, vectors, strict=False):
                document.embedding = embedding
            self.tracer.end_run(
                embed_run_id,
                outputs={"vectorCount": len(vectors), "dimensions": len(vectors[0]) if vectors else 0},
                metadata={"stage": "embed"},
            )

            persist_run_id = self.tracer.start_run(
                name="memory.persist",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"documentCount": len(result.documents), "sessionId": session_id},
                metadata={"stage": "persist"},
                tags=["memory", "persist"],
            )
            self.store.save_compaction(result.compaction)
            self.store.replace_session_documents(session_id, result.documents)
            index_state = self._rebuild_vector_index()
            self.tracer.end_run(
                persist_run_id,
                outputs={
                    "documentCount": len(result.documents),
                    "indexBackend": str(index_state.get("backend") or "none"),
                },
                metadata={"stage": "persist"},
            )
            payload: dict[str, object] = {
                "sessionId": session_id,
                "summary": result.compaction.summary,
                "facts": result.compaction.facts,
                "documentCount": len(result.documents),
                "sourceItemCount": result.compaction.source_item_count,
                "updatedAt": result.compaction.updated_at,
                "indexBackend": str(index_state.get("backend") or "none"),
            }
            self.tracer.end_run(
                run_id,
                outputs={
                    "sessionId": session_id,
                    "documentCount": len(result.documents),
                    "indexBackend": str(index_state.get("backend") or "none"),
                },
                metadata={"module": "memory"},
            )
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"sessionId": session_id},
                error=(str(exc).strip() or "memory compaction failed")[:1200],
                metadata={"module": "memory"},
                tags=["error"],
            )
            raise

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemorySearchResult]:
        run_id = self.tracer.start_run(
            name="memory.search",
            run_type="chain",
            inputs={"query": query, "limit": max(1, int(limit)), "sessionId": session_id or ""},
            metadata={"module": "memory"},
            tags=["memory", "search"],
        )
        query_text = query.strip()
        if not query_text:
            self.tracer.end_run(
                run_id,
                outputs={"itemCount": 0, "reason": "empty_query"},
                metadata={"module": "memory"},
            )
            return []
        try:
            embed_run_id = self.tracer.start_run(
                name="memory.search_embed_query",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"queryLength": len(query_text)},
                metadata={"stage": "embed_query"},
                tags=["memory", "embed"],
            )
            query_embedding = self._embed_query(query_text)
            self.tracer.end_run(
                embed_run_id,
                outputs={"dimensions": len(query_embedding)},
                metadata={"stage": "embed_query"},
            )
            retrieve_run_id = self.tracer.start_run(
                name="memory.search_retrieve",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"limit": max(1, int(limit)), "sessionId": session_id or ""},
                metadata={"stage": "retrieve"},
                tags=["memory", "retrieve"],
            )
            results = self._search_by_index(query_embedding=query_embedding, limit=max(1, int(limit)), session_id=session_id)
            if not results:
                results = self.store.search(query_embedding=query_embedding, limit=limit, session_id=session_id)
            self.tracer.end_run(
                retrieve_run_id,
                outputs={"itemCount": len(results)},
                metadata={"stage": "retrieve"},
            )
            self.tracer.end_run(
                run_id,
                outputs={"itemCount": len(results), "sessionId": session_id or ""},
                metadata={"module": "memory"},
            )
            return results
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"sessionId": session_id or ""},
                error=(str(exc).strip() or "memory search failed")[:1200],
                metadata={"module": "memory"},
                tags=["error"],
            )
            raise

    def reindex(self) -> dict[str, object]:
        state = self._rebuild_vector_index()
        return {
            "indexBackend": str(state.get("backend") or "none"),
            "documentCount": int(state.get("documentCount") or 0),
            "dimensions": int(state.get("dimension") or 0),
        }

    def _embed_query(self, query_text: str) -> list[float]:
        try:
            vector = self.embedder.embed_text(query_text)
            if vector:
                return vector
        except Exception:
            pass
        return self.fallback_embedder.embed_text(query_text)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self.embedder.embed_texts(texts)
            if vectors and len(vectors) == len(texts):
                return vectors
        except Exception:
            pass
        return self.fallback_embedder.embed_texts(texts)

    def _build_default_embedder(self) -> TextEmbedder:
        config = load_config()
        embedding_provider = os.environ.get("ORCHESTRATOR_EMBEDDING_PROVIDER", "openai_compat").strip().lower()
        embedding_model = os.environ.get("ORCHESTRATOR_EMBEDDING_MODEL", "text-embedding-3-large").strip()
        api_key = os.environ.get("ORCHESTRATOR_EMBEDDING_API_KEY", config.planner.api_key).strip()
        api_base = os.environ.get("ORCHESTRATOR_EMBEDDING_API_BASE", config.planner.api_base).strip()
        if embedding_provider in {"hash", "local_hash"}:
            return HashedTokenEmbedder()
        if not api_key or not api_base:
            return HashedTokenEmbedder()
        if embedding_provider in {"openai_compat", "openai-compatible", "openai"}:
            return OpenAICompatEmbedder(
                api_key=api_key,
                api_base=api_base,
                model=embedding_model or "text-embedding-3-large",
            )
        return HashedTokenEmbedder()

    def _search_by_index(
        self,
        *,
        query_embedding: list[float],
        limit: int,
        session_id: str | None,
    ) -> list[MemorySearchResult]:
        scores = self.vector_index.search(
            query_vectors=[query_embedding],
            limit=max(limit * 8, limit),
            session_id=session_id,
        )
        if not scores:
            rebuilt = self._rebuild_vector_index()
            if str(rebuilt.get("backend") or "none") == "none":
                return []
            scores = self.vector_index.search(
                query_vectors=[query_embedding],
                limit=max(limit * 8, limit),
                session_id=session_id,
            )
        if not scores:
            return []
        ranked_pairs = sorted(scores.items(), key=lambda item: float(item[1]), reverse=True)
        records = self.store.list_documents_by_ids(
            document_ids=[document_id for document_id, _ in ranked_pairs],
            session_id=session_id,
        )
        by_id = {record.document_id: record for record in records}
        results: list[MemorySearchResult] = []
        for document_id, score in ranked_pairs:
            record = by_id.get(document_id)
            if record is None:
                continue
            results.append(
                MemorySearchResult(
                    document_id=record.document_id,
                    session_id=record.session_id,
                    document_type=record.document_type,
                    title=record.title,
                    content=record.content,
                    metadata=dict(record.metadata),
                    score=float(score),
                    updated_at=record.updated_at,
                )
            )
            if len(results) >= max(1, limit):
                break
        return results

    def _rebuild_vector_index(self) -> dict[str, object]:
        documents = self.store.list_documents_for_index()
        try:
            return self.vector_index.rebuild(documents=documents)
        except Exception:
            return {"backend": "none", "documentCount": 0, "dimension": 0}

    def cleanup(self) -> dict[str, int]:
        payload = self.store.cleanup_documents()
        self._rebuild_vector_index()
        return payload
