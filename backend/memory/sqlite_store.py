from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from pathlib import Path
import json
import sqlite3

from backend.memory.models import MemoryCompaction, MemoryDocument, MemorySearchResult


class SQLiteMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
        for row in rows:
            embedding = json.loads(row["embedding_json"])
            score = self._cosine_similarity(query_embedding, embedding)
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

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
