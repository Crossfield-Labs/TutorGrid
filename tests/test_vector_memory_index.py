from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.vector import MemoryVectorIndex


class MemoryVectorIndexTests(unittest.TestCase):
    def test_json_backend_rebuild_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index = MemoryVectorIndex(root=Path(temp_dir), backend="json")
            payload = index.rebuild(
                documents=[
                    {"documentId": "doc-1", "sessionId": "s1", "embedding": [1.0, 0.0]},
                    {"documentId": "doc-2", "sessionId": "s1", "embedding": [0.3, 0.7]},
                    {"documentId": "doc-3", "sessionId": "s2", "embedding": [0.0, 1.0]},
                ]
            )
            self.assertEqual(payload["backend"], "json")
            scores = index.search(query_vectors=[[1.0, 0.0]], limit=2)
            self.assertEqual(len(scores), 2)
            self.assertGreater(scores.get("doc-1", 0.0), scores.get("doc-2", 0.0))

    def test_json_backend_search_with_session_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index = MemoryVectorIndex(root=Path(temp_dir), backend="json")
            index.rebuild(
                documents=[
                    {"documentId": "doc-a", "sessionId": "session-a", "embedding": [1.0, 0.0]},
                    {"documentId": "doc-b", "sessionId": "session-b", "embedding": [1.0, 0.0]},
                ]
            )
            scores = index.search(query_vectors=[[1.0, 0.0]], limit=5, session_id="session-a")
            self.assertEqual(set(scores.keys()), {"doc-a"})


if __name__ == "__main__":
    unittest.main()

