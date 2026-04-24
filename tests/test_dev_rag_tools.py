from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from backend.dev.benchmark_ingest import run_benchmark
from backend.dev.evaluate_rag import run_evaluation


class DevRagToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_evaluation_with_local_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "observer.md").write_text(
                (
                    "Observer pattern defines one-to-many dependency.\n"
                    "Observers are notified through publish-subscribe flow.\n"
                ),
                encoding="utf-8",
            )
            dataset = {
                "courseName": "Patterns",
                "documents": [{"path": "docs/observer.md"}],
                "queries": [
                    {
                        "question": "What is observer pattern?",
                        "expectedPhrases": ["one-to-many dependency", "publish-subscribe"],
                        "limit": 5,
                    }
                ],
            }
            dataset_path = root / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            args = SimpleNamespace(
                dataset=str(dataset_path),
                db_path=str(root / "orchestrator.sqlite3"),
                kb_root=str(root / "knowledge_bases"),
                course_name="",
                course_description="",
                chunk_size=900,
                default_limit=8,
                ks="1,3,5",
                max_queries=0,
                reuse_course_id="",
                output="",
            )
            output = await run_evaluation(args)
            self.assertEqual(output["ingest"]["successFiles"], 1)
            self.assertEqual(output["queries"]["totalQueries"], 1)
            self.assertEqual(output["queries"]["evaluatedQueries"], 1)
            self.assertGreaterEqual(output["metrics"]["recallAtK"]["R@5"], 1.0)


class IngestBenchmarkScriptTests(unittest.TestCase):
    def test_run_benchmark_with_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "strategy.md").write_text(
                "Strategy pattern encapsulates algorithms and allows runtime switching.",
                encoding="utf-8",
            )
            manifest = {"documents": [{"path": "docs/strategy.md", "name": "strategy"}]}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            args = SimpleNamespace(
                paths=[],
                manifest=str(manifest_path),
                db_path=str(root / "orchestrator.sqlite3"),
                kb_root=str(root / "knowledge_bases"),
                course_name="bench",
                course_description="",
                chunk_size=900,
                output="",
            )
            output = run_benchmark(args)
            self.assertEqual(output["summary"]["totalFiles"], 1)
            self.assertEqual(output["summary"]["successFiles"], 1)
            self.assertGreaterEqual(output["summary"]["totalChunks"], 1)


if __name__ == "__main__":
    unittest.main()
