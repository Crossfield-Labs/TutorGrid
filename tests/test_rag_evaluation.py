from __future__ import annotations

import unittest

from backend.rag.evaluation import RagEvalResult, aggregate_rag_metrics, find_first_relevant_rank


class RagEvaluationTests(unittest.TestCase):
    def test_find_first_relevant_rank(self) -> None:
        items = [
            {"content": "intro material"},
            {"content": "observer pattern uses publish-subscribe"},
            {"content": "other"},
        ]
        rank = find_first_relevant_rank(items, ["Publish-Subscribe"])
        self.assertEqual(rank, 2)

    def test_find_first_relevant_rank_returns_none_when_missing(self) -> None:
        items = [{"content": "raft consensus"}, {"content": "leader election"}]
        rank = find_first_relevant_rank(items, ["observer"])
        self.assertIsNone(rank)

    def test_aggregate_rag_metrics(self) -> None:
        results = [
            RagEvalResult(
                question="q1",
                expected_phrases=["one-to-many"],
                first_relevant_rank=1,
                retrieved_count=5,
                latency_ms=20.0,
            ),
            RagEvalResult(
                question="q2",
                expected_phrases=["publish-subscribe"],
                first_relevant_rank=3,
                retrieved_count=5,
                latency_ms=40.0,
            ),
            RagEvalResult(
                question="q3",
                expected_phrases=["observer"],
                first_relevant_rank=None,
                retrieved_count=5,
                latency_ms=60.0,
            ),
        ]
        metrics = aggregate_rag_metrics(results, ks=[1, 3, 5])
        self.assertEqual(metrics["totalQueries"], 3)
        self.assertAlmostEqual(metrics["mrr"], (1.0 + (1.0 / 3.0)) / 3.0, places=6)
        self.assertAlmostEqual(metrics["meanLatencyMs"], 40.0, places=6)
        self.assertAlmostEqual(metrics["recallAtK"]["R@1"], 1.0 / 3.0, places=6)
        self.assertAlmostEqual(metrics["recallAtK"]["R@3"], 2.0 / 3.0, places=6)
        self.assertEqual(metrics["hitCountAtK"]["R@5"], 2)


if __name__ == "__main__":
    unittest.main()
