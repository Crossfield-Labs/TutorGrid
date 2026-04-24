from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from pathlib import Path
import json
import os
import sqlite3
from typing import Any

from backend.memory.models import MemoryCompaction, MemoryDocument, MemorySearchResult
from backend.vector import VectorRanker


class SQLiteMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        vector_backend = os.environ.get("ORCHESTRATOR_VECTOR_STORE_BACKEND", "auto").strip().lower()
        self.vector_ranker = VectorRanker(backend=vector_backend)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_compactions (
                    session_id TEXT PRIMARY KEY,
                    summary_text TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    source_item_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_documents (
                    document_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memory_documents_session_id
                ON memory_documents(session_id, updated_at DESC);
                """
            )
            connection.commit()

    def save_compaction(self, compaction: MemoryCompaction) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO memory_compactions (
                    session_id, summary_text, facts_json, source_item_count, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary_text=excluded.summary_text,
                    facts_json=excluded.facts_json,
                    source_item_count=excluded.source_item_count,
                    updated_at=excluded.updated_at
                """,
                (
                    compaction.session_id,
                    compaction.summary,
                    json.dumps(compaction.facts, ensure_ascii=False),
                    compaction.source_item_count,
                    compaction.updated_at,
                ),
            )
            connection.commit()

    def replace_session_documents(self, session_id: str, documents: list[MemoryDocument]) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM memory_documents WHERE session_id = ?", (session_id,))
            for document in documents:
                record = asdict(document)
                connection.execute(
                    """
                    INSERT INTO memory_documents (
                        document_id, session_id, document_type, title, content,
                        metadata_json, embedding_json, token_estimate, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["document_id"],
                        record["session_id"],
                        record["document_type"],
                        record["title"],
                        record["content"],
                        json.dumps(record["metadata"], ensure_ascii=False),
                        json.dumps(record["embedding"], ensure_ascii=False),
                        record["token_estimate"],
                        record["created_at"],
                        record["updated_at"],
                    ),
                )
            connection.commit()

    def list_session_documents(self, session_id: str) -> list[MemoryDocument]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM memory_documents
                WHERE session_id = ?
                ORDER BY updated_at DESC, document_id ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def cleanup_documents(self) -> dict[str, int]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT document_id, session_id, document_type, title, content
                FROM memory_documents
                ORDER BY updated_at DESC, document_id DESC
                """
            ).fetchall()
            seen: set[tuple[str, str, str, str]] = set()
            duplicates: list[str] = []
            empty_documents: list[str] = []
            for row in rows:
                title = str(row["title"] or "").strip()
                content = str(row["content"] or "").strip()
                if not title and not content:
                    empty_documents.append(str(row["document_id"]))
                    continue
                key = (
                    str(row["session_id"] or ""),
                    str(row["document_type"] or ""),
                    title.lower(),
                    content.lower(),
                )
                if key in seen:
                    duplicates.append(str(row["document_id"]))
                    continue
                seen.add(key)

            deleted = duplicates + empty_documents
            if deleted:
                placeholders = ",".join(["?"] * len(deleted))
                connection.execute(
                    f"DELETE FROM memory_documents WHERE document_id IN ({placeholders})",
                    tuple(deleted),
                )
            connection.commit()

        return {
            "deletedDocuments": len(deleted),
            "duplicateDocuments": len(duplicates),
            "emptyDocuments": len(empty_documents),
        }

    def list_documents_for_index(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT document_id, session_id, embedding_json
                FROM memory_documents
                ORDER BY updated_at DESC
                """
            ).fetchall()
        documents: list[dict[str, Any]] = []
        for row in rows:
            try:
                embedding = json.loads(row["embedding_json"] or "[]")
            except Exception:
                embedding = []
            documents.append(
                {
                    "documentId": str(row["document_id"]),
                    "sessionId": str(row["session_id"]),
                    "embedding": embedding if isinstance(embedding, list) else [],
                }
            )
        return documents

    def list_documents_by_ids(
        self,
        *,
        document_ids: list[str],
        session_id: str | None = None,
    ) -> list[MemorySearchResult]:
        normalized_ids = [str(item or "").strip() for item in document_ids if str(item or "").strip()]
        if not normalized_ids:
            return []
        placeholders = ",".join(["?"] * len(normalized_ids))
        params: list[Any] = list(normalized_ids)
        where_clause = f"document_id IN ({placeholders})"
        if session_id:
            where_clause += " AND session_id = ?"
            params.append(session_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM memory_documents
                WHERE {where_clause}
                """,
                tuple(params),
            ).fetchall()
        return [
            MemorySearchResult(
                document_id=str(row["document_id"]),
                session_id=str(row["session_id"]),
                document_type=str(row["document_type"]),
                title=str(row["title"]),
                content=str(row["content"]),
                metadata=json.loads(row["metadata_json"] or "{}"),
                score=0.0,
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def search(
        self,
        *,
        query_embedding: list[float],
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemorySearchResult]:
        with closing(self._connect()) as connection:
            if session_id:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM memory_documents
                    WHERE session_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (session_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM memory_documents
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        scored_results: list[MemorySearchResult] = []
        embeddings = [json.loads(row["embedding_json"] or "[]") for row in rows]
        scores = self.vector_ranker.rank_max_similarity(query_vectors=[query_embedding], document_vectors=embeddings)
        for row, score in zip(rows, scores, strict=False):
            if score <= 0:
                continue
            scored_results.append(
                MemorySearchResult(
                    document_id=str(row["document_id"]),
                    session_id=str(row["session_id"]),
                    document_type=str(row["document_type"]),
                    title=str(row["title"]),
                    content=str(row["content"]),
                    metadata=json.loads(row["metadata_json"] or "{}"),
                    score=score,
                    updated_at=str(row["updated_at"]),
                )
            )
        scored_results.sort(key=lambda item: item.score, reverse=True)
        return scored_results[: max(1, limit)]

    def _row_to_document(self, row: sqlite3.Row) -> MemoryDocument:
        return MemoryDocument(
            document_id=str(row["document_id"]),
            session_id=str(row["session_id"]),
            document_type=str(row["document_type"]),
            title=str(row["title"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            embedding=json.loads(row["embedding_json"] or "[]"),
            token_estimate=int(row["token_estimate"] or 0),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
