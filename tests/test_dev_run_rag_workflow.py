from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from backend.dev.run_rag_workflow import run_workflow


class RunRagWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_workflow_generates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "observer.md").write_text(
                (
                    "Observer pattern defines one-to-many dependency.\n"
                    "Subscribers are notified in publish-subscribe style.\n"
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
                        "limit": 8,
                    }
                ],
            }
            dataset_path = root / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

            profiles = {
                "profiles": [
                    {
                        "name": "baseline",
                        "description": "baseline only",
                        "env": {
                            "ORCHESTRATOR_RAG_MULTI_QUERY": "0",
                            "ORCHESTRATOR_RAG_HYDE": "0",
                            "ORCHESTRATOR_RAG_RERANK": "0",
                        },
                    }
                ]
            }
            profiles_path = root / "profiles.json"
            profiles_path.write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")

            args = SimpleNamespace(
                dataset=str(dataset_path),
                profiles=str(profiles_path),
                chunk_sizes="600,900",
                default_limit=8,
                ks="1,3,5",
                max_queries=0,
                top_n=3,
                chunk_size_compare=900,
                strict_validate=False,
                run_root=str(root / "runs"),
                run_name="test_run",
            )
            output = await run_workflow(args)

            self.assertIn("artifacts", output)
            artifacts = output["artifacts"]
            self.assertTrue(Path(artifacts["profileCompareJson"]).exists())
            self.assertTrue(Path(artifacts["gridReportJson"]).exists())
            self.assertTrue(Path(artifacts["recommendationJson"]).exists())
            self.assertEqual(output["recommended"]["profile"], "baseline")


if __name__ == "__main__":
    unittest.main()
