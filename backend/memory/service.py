from __future__ import annotations

from pathlib import Path

from backend.memory.compression import SessionMemoryCompressor
from backend.memory.embedding import HashedTokenEmbedder
from backend.memory.models import MemorySearchResult
from backend.memory.sqlite_store import SQLiteMemoryStore


class MemoryService:
    def __init__(
        self,
        *,
        store: SQLiteMemoryStore | None = None,
        embedder: HashedTokenEmbedder | None = None,
        compressor: SessionMemoryCompressor | None = None,
        path: Path | None = None,
    ) -> None:
        db_path = path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        self.store = store or SQLiteMemoryStore(db_path)
        self.embedder = embedder or HashedTokenEmbedder()
        self.compressor = compressor or SessionMemoryCompressor()

    def compact_session(
        self,
        *,
        session_id: str,
        task: str,
        goal: str,
        history_items: list[dict[str, object]],
    ) -> dict[str, object]:
        result = self.compressor.compress_session(
            session_id=session_id,
            task=task,
            goal=goal,
            history_items=history_items,
        )
        for document in result.documents:
            document.embedding = self.embedder.embed_text(f"{document.title}\n{document.content}")
        self.store.save_compaction(result.compaction)
        self.store.replace_session_documents(session_id, result.documents)
        return {
            "sessionId": session_id,
            "summary": result.compaction.summary,
            "facts": result.compaction.facts,
            "documentCount": len(result.documents),
            "sourceItemCount": result.compaction.source_item_count,
            "updatedAt": result.compaction.updated_at,
        }

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemorySearchResult]:
        query_text = query.strip()
        if not query_text:
            return []
        query_embedding = self.embedder.embed_text(query_text)
        return self.store.search(query_embedding=query_embedding, limit=limit, session_id=session_id)

    def cleanup(self) -> dict[str, int]:
        return self.store.cleanup_documents()
