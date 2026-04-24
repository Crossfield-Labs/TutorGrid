from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.vector import KnowledgeVectorIndex


class KnowledgeVectorIndexTests(unittest.TestCase):
    def test_json_backend_rebuild_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index = KnowledgeVectorIndex(root=root, backend="json")
            rebuild = index.rebuild_course(
                course_id="course-1",
                chunks=[
                    {"chunkId": "chunk-a", "embedding": [1.0, 0.0]},
                    {"chunkId": "chunk-b", "embedding": [0.3, 0.7]},
                    {"chunkId": "chunk-c", "embedding": [0.0, 1.0]},
                ],
            )
            self.assertEqual(rebuild["backend"], "json")
            self.assertEqual(rebuild["chunkCount"], 3)

            scores = index.search(course_id="course-1", query_vectors=[[1.0, 0.0]], limit=2)
            self.assertEqual(len(scores), 2)
            self.assertGreater(scores.get("chunk-a", 0.0), scores.get("chunk-b", 0.0))

    def test_delete_course_removes_index_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index = KnowledgeVectorIndex(root=root, backend="json")
            index.rebuild_course(
                course_id="course-2",
                chunks=[{"chunkId": "chunk-a", "embedding": [1.0, 0.0]}],
            )
            index_dir = root / "course-2" / "index"
            self.assertTrue(index_dir.exists())
            index.delete_course(course_id="course-2")
            self.assertFalse(index_dir.exists())


if __name__ == "__main__":
    unittest.main()

