from __future__ import annotations

import os
import unittest

from backend.dev.compare_rag_profiles import pick_best_profile, render_markdown_table, temporary_env


class CompareRagProfilesTests(unittest.TestCase):
    def test_temporary_env_restores_original_value(self) -> None:
        key = "ORCHESTRATOR_RAG_TEST_TMP"
        os.environ[key] = "original"
        with temporary_env({key: "override"}):
            self.assertEqual(os.environ.get(key), "override")
        self.assertEqual(os.environ.get(key), "original")
        os.environ.pop(key, None)

    def test_render_markdown_table(self) -> None:
        table = render_markdown_table(
            [
                {
                    "name": "baseline",
                    "metrics": {
                        "mrr": 0.25,
                        "meanLatencyMs": 10.0,
                        "totalQueries": 3,
                        "recallAtK": {"R@1": 0.0, "R@3": 0.66, "R@5": 1.0},
                    },
                }
            ]
        )
        self.assertIn("| Profile | MRR |", table)
        self.assertIn("| baseline | 0.2500 |", table)

    def test_pick_best_profile_prefers_higher_mrr(self) -> None:
        best = pick_best_profile(
            [
                {"name": "a", "metrics": {"mrr": 0.3, "recallAtK": {"R@3": 0.7}, "meanLatencyMs": 8.0}},
                {"name": "b", "metrics": {"mrr": 0.5, "recallAtK": {"R@3": 0.5}, "meanLatencyMs": 20.0}},
            ]
        )
        self.assertIsNotNone(best)
        self.assertEqual(best["name"], "b")


if __name__ == "__main__":
    unittest.main()
