from __future__ import annotations

import unittest

from backend.dev.tune_rag_grid import parse_chunk_sizes, rank_variants, render_markdown_table, variant_score


class TuneRagGridTests(unittest.TestCase):
    def test_parse_chunk_sizes(self) -> None:
        values = parse_chunk_sizes("100, 600,900,abc,1200")
        self.assertEqual(values, [200, 600, 900, 1200])

    def test_variant_score_prefers_higher_quality(self) -> None:
        score_low = variant_score(
            {"mrr": 0.2, "meanLatencyMs": 10.0, "recallAtK": {"R@1": 0.0, "R@3": 0.2, "R@5": 0.3}}
        )
        score_high = variant_score(
            {"mrr": 0.5, "meanLatencyMs": 20.0, "recallAtK": {"R@1": 0.1, "R@3": 0.8, "R@5": 1.0}}
        )
        self.assertGreater(score_high, score_low)

    def test_rank_variants(self) -> None:
        variants = [
            {"chunkSize": 900, "profile": "a", "score": 20.0, "metrics": {"mrr": 0.2, "recallAtK": {"R@3": 0.6}, "meanLatencyMs": 10.0}},
            {"chunkSize": 600, "profile": "b", "score": 30.0, "metrics": {"mrr": 0.4, "recallAtK": {"R@3": 0.6}, "meanLatencyMs": 12.0}},
        ]
        ranked = rank_variants(variants)
        self.assertEqual(ranked[0]["profile"], "b")

    def test_render_markdown_table(self) -> None:
        markdown = render_markdown_table(
            [
                {
                    "chunkSize": 900,
                    "profile": "baseline",
                    "score": 33.3,
                    "metrics": {"mrr": 0.3, "meanLatencyMs": 2.0, "recallAtK": {"R@1": 0.0, "R@3": 1.0, "R@5": 1.0}},
                }
            ],
            top_n=3,
        )
        self.assertIn("| Rank | Chunk Size | Profile |", markdown)
        self.assertIn("| 1 | 900 | baseline |", markdown)


if __name__ == "__main__":
    unittest.main()
