from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.db.models import MemoryCompactionModel, MemoryDocumentModel
from backend.db.session import OrchestratorDatabase
from backend.memory.models import MemoryCompaction, MemoryDocument, MemorySearchResult


class SQLiteMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.database = OrchestratorDatabase(path)

    def save_compaction(self, compaction: MemoryCompaction) -> None:
        with self.database.SessionLocal() as db:
            statement = sqlite_insert(MemoryCompactionModel).values(
                session_id=compaction.session_id,
                summary_text=compaction.summary,
                facts_json=compaction.facts,
                source_item_count=compaction.source_item_count,
                updated_at=compaction.updated_at,
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["session_id"],
                    set_={
                        "summary_text": compaction.summary,
                        "facts_json": compaction.facts,
                        "source_item_count": compaction.source_item_count,
                        "updated_at": compaction.updated_at,
                    },
                )
            )
            db.commit()

    def replace_session_documents(self, session_id: str, documents: list[MemoryDocument]) -> None:
        with self.database.SessionLocal() as db:
            db.execute(delete(MemoryDocumentModel).where(MemoryDocumentModel.session_id == session_id))
            if documents:
                db.add_all(
                    [
                        MemoryDocumentModel(
                            document_id=document.document_id,
                            session_id=document.session_id,
                            document_type=document.document_type,
                            title=document.title,
                            content=document.content,
                            metadata_json=document.metadata,
                            embedding_json=document.embedding,
                            token_estimate=document.token_estimate,
                            created_at=document.created_at,
                            updated_at=document.updated_at,
                        )
                        for document in documents
                    ]
                )
            db.commit()

    def list_session_documents(self, session_id: str) -> list[MemoryDocument]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(MemoryDocumentModel)
                .where(MemoryDocumentModel.session_id == session_id)
                .order_by(MemoryDocumentModel.updated_at.desc(), MemoryDocumentModel.document_id.asc())
            ).all()
        return [self._row_to_document(row) for row in rows]

    def cleanup_documents(self) -> dict[str, int]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(MemoryDocumentModel).order_by(MemoryDocumentModel.updated_at.desc(), MemoryDocumentModel.document_id.desc())
            ).all()
            seen: set[tuple[str, str, str, str]] = set()
            duplicates: list[str] = []
            empty_documents: list[str] = []
            for row in rows:
                title = (row.title or "").strip()
                content = (row.content or "").strip()
                if not title and not content:
                    empty_documents.append(row.document_id)
                    continue
                key = (
                    row.session_id,
                    row.document_type,
                    title.lower(),
                    content.lower(),
                )
                if key in seen:
                    duplicates.append(row.document_id)
                    continue
                seen.add(key)
            deleted = duplicates + empty_documents
            if deleted:
                db.execute(delete(MemoryDocumentModel).where(MemoryDocumentModel.document_id.in_(deleted)))
            db.commit()
        return {
            "deletedDocuments": len(deleted),
            "duplicateDocuments": len(duplicates),
            "emptyDocuments": len(empty_documents),
        }

    def list_documents_for_index(self) -> list[dict[str, Any]]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(select(MemoryDocumentModel).order_by(MemoryDocumentModel.updated_at.desc())).all()
        return [
            {
                "documentId": row.document_id,
                "sessionId": row.session_id,
                "embedding": list(row.embedding_json or []),
            }
            for row in rows
        ]

    def list_documents_by_ids(
        self,
        *,
        document_ids: list[str],
        session_id: str | None = None,
    ) -> list[MemorySearchResult]:
        normalized_ids = [str(item or "").strip() for item in document_ids if str(item or "").strip()]
        if not normalized_ids:
            return []
        with self.database.SessionLocal() as db:
            statement = select(MemoryDocumentModel).where(MemoryDocumentModel.document_id.in_(normalized_ids))
            if session_id:
                statement = statement.where(MemoryDocumentModel.session_id == session_id)
            rows = db.scalars(statement).all()
        return [
            MemorySearchResult(
                document_id=row.document_id,
                session_id=row.session_id,
                document_type=row.document_type,
                title=row.title,
                content=row.content,
                metadata=dict(row.metadata_json or {}),
                score=0.0,
                updated_at=row.updated_at,
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
        with self.database.SessionLocal() as db:
            statement = select(MemoryDocumentModel).order_by(MemoryDocumentModel.updated_at.desc())
            if session_id:
                statement = statement.where(MemoryDocumentModel.session_id == session_id)
            rows = db.scalars(statement).all()
        scored_results: list[MemorySearchResult] = []
        for row in rows:
            score = self._cosine_similarity(query_embedding, list(row.embedding_json or []))
            if score <= 0:
                continue
            scored_results.append(
                MemorySearchResult(
                    document_id=row.document_id,
                    session_id=row.session_id,
                    document_type=row.document_type,
                    title=row.title,
                    content=row.content,
                    metadata=dict(row.metadata_json or {}),
                    score=score,
                    updated_at=row.updated_at,
                )
            )
        scored_results.sort(key=lambda item: item.score, reverse=True)
        return scored_results[: max(1, limit)]

    def _row_to_document(self, row: MemoryDocumentModel) -> MemoryDocument:
        return MemoryDocument(
            document_id=row.document_id,
            session_id=row.session_id,
            document_type=row.document_type,
            title=row.title,
            content=row.content,
            metadata=dict(row.metadata_json or {}),
            embedding=list(row.embedding_json or []),
            token_estimate=row.token_estimate,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
