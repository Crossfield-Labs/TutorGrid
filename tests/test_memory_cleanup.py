from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.memory.embedding import HashedTokenEmbedder
from backend.memory.models import MemoryDocument
from backend.memory.service import MemoryService
from backend.memory.sqlite_store import SQLiteMemoryStore


class MemoryCleanupTests(unittest.TestCase):
    def test_cleanup_removes_duplicate_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteMemoryStore(Path(temp_dir) / "memory.sqlite3")
            service = MemoryService(store=store, embedder=HashedTokenEmbedder())
            document_a = MemoryDocument(
                document_id="doc-a",
                session_id="session-1",
                document_type="summary",
                title="Longest palindrome",
                content="Manacher algorithm in O(n).",
                metadata={},
                embedding=[1.0, 0.0],
                token_estimate=8,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:01+00:00",
            )
            document_b = MemoryDocument(
                document_id="doc-b",
                session_id="session-1",
                document_type="summary",
                title="Longest palindrome",
                content="Manacher algorithm in O(n).",
                metadata={},
                embedding=[1.0, 0.0],
                token_estimate=8,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )

            store.replace_session_documents("session-1", [document_a, document_b])

            cleanup = service.cleanup()
            documents = store.list_session_documents("session-1")

            self.assertEqual(cleanup["duplicateDocuments"], 1)
            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0].document_id, "doc-a")


if __name__ == "__main__":
    unittest.main()
