from __future__ import annotations

import unittest

from backend.dev.summarize_rag_reports import build_recommendation, render_markdown


class SummarizeRagReportsTests(unittest.TestCase):
    def test_build_recommendation(self) -> None:
        profile_report = {
            "datasetPath": "dataset.json",
            "profiles": [
                {"name": "baseline", "metrics": {"mrr": 0.3, "meanLatencyMs": 10.0, "recallAtK": {"R@3": 0.7}}},
                {"name": "full_rag", "metrics": {"mrr": 0.35, "meanLatencyMs": 12.0, "recallAtK": {"R@3": 0.7}}},
            ],
            "bestProfile": {"name": "baseline", "metrics": {"mrr": 0.3, "meanLatencyMs": 10.0, "recallAtK": {"R@3": 0.7}}},
        }
        grid_report = {
            "datasetPath": "dataset.json",
            "variants": [
                {
                    "chunkSize": 900,
                    "profile": "baseline",
                    "score": 60.0,
                    "metrics": {"mrr": 0.3, "meanLatencyMs": 10.0, "recallAtK": {"R@3": 0.7}},
                }
            ],
            "best": {
                "chunkSize": 900,
                "profile": "baseline",
                "score": 60.0,
                "metrics": {"mrr": 0.3, "meanLatencyMs": 10.0, "recallAtK": {"R@3": 0.7}},
            },
        }
        summary = build_recommendation(profile_report=profile_report, grid_report=grid_report)
        self.assertEqual(summary["recommended"]["chunkSize"], 900)
        self.assertEqual(summary["recommended"]["profile"], "baseline")
        self.assertEqual(summary["variantCount"], 1)

    def test_render_markdown(self) -> None:
        summary = {
            "generatedAt": "2026-01-01T00:00:00+00:00",
            "datasetPath": "dataset.json",
            "recommended": {"chunkSize": 900, "profile": "baseline", "score": 60.0, "mrr": 0.3, "recallAt3": 0.7, "latencyMs": 10.0},
            "profileSummary": {
                "bestVsBaseline": {"deltaMRR": 0.0, "deltaR3": 0.0, "deltaLatencyMs": 0.0},
                "fullRagVsBaseline": {"deltaMRR": 0.05, "deltaLatencyMs": 2.0},
            },
            "topVariants": [
                {
                    "chunkSize": 900,
                    "profile": "baseline",
                    "score": 60.0,
                    "metrics": {"mrr": 0.3, "meanLatencyMs": 10.0, "recallAtK": {"R@3": 0.7}},
                }
            ],
        }
        markdown = render_markdown(summary)
        self.assertIn("# RAG Tuning Recommendation", markdown)
        self.assertIn("| Rank | Chunk Size | Profile |", markdown)
        self.assertIn("`900`", markdown)


if __name__ == "__main__":
    unittest.main()
