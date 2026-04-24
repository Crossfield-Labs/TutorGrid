from __future__ import annotations

import unittest

from backend.vector import VectorRanker


class VectorRankerTests(unittest.TestCase):
    def test_python_backend_scores_by_max_similarity(self) -> None:
        ranker = VectorRanker(backend="python")
        scores = ranker.rank_max_similarity(
            query_vectors=[[1.0, 0.0], [0.0, 1.0]],
            document_vectors=[[1.0, 0.0], [0.2, 0.8], [-1.0, 0.0], []],
        )
        self.assertEqual(len(scores), 4)
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], scores[3])
        self.assertEqual(scores[2], 0.0)

    def test_faiss_backend_gracefully_falls_back(self) -> None:
        ranker = VectorRanker(backend="faiss")
        scores = ranker.rank_max_similarity(
            query_vectors=[[0.5, 0.5]],
            document_vectors=[[0.5, 0.5], [0.1, 0.1], [1.0]],
        )
        self.assertEqual(len(scores), 3)
        self.assertGreaterEqual(scores[0], scores[1])
        self.assertEqual(scores[2], 0.0)


if __name__ == "__main__":
    unittest.main()
