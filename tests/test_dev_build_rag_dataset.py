from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from backend.dev.build_rag_dataset import build_dataset


class BuildRagDatasetTests(unittest.TestCase):
    def test_build_dataset_from_csv_and_doc_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "doc1.md"
            doc.write_text("observer", encoding="utf-8")
            csv_path = root / "questions.csv"
            csv_path.write_text(
                (
                    "id,question,expected_phrases,limit,difficulty,type,notes\n"
                    "q1,What is observer?,one-to-many dependency|publish-subscribe,8,easy,definition,note\n"
                ),
                encoding="utf-8",
            )
            dataset, problems, warnings = build_dataset(
                course_name="Patterns",
                course_description="test",
                questions_csv=csv_path,
                doc_paths=[str(doc)],
                doc_manifest="",
                chunk_size=900,
                default_limit=8,
                strict=True,
            )
            self.assertFalse(problems)
            self.assertFalse(warnings)
            self.assertEqual(dataset["courseName"], "Patterns")
            self.assertEqual(len(dataset["documents"]), 1)
            self.assertEqual(len(dataset["queries"]), 1)
            self.assertEqual(dataset["queries"][0]["expectedPhrases"], ["one-to-many dependency", "publish-subscribe"])

    def test_build_dataset_manifest_and_non_strict_missing_doc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "questions.csv"
            csv_path.write_text(
                "question,expected_phrases\nWhat is strategy?,encapsulate algorithms\n",
                encoding="utf-8",
            )
            manifest_path = root / "docs.json"
            manifest_path.write_text(json.dumps(["missing.md"]), encoding="utf-8")
            dataset, problems, warnings = build_dataset(
                course_name="Patterns",
                course_description="",
                questions_csv=csv_path,
                doc_paths=[],
                doc_manifest=str(manifest_path),
                chunk_size=900,
                default_limit=8,
                strict=False,
            )
            self.assertFalse(problems)
            self.assertTrue(warnings)
            self.assertEqual(len(dataset["documents"]), 0)
            self.assertEqual(len(dataset["queries"]), 1)

    def test_build_dataset_strict_requires_expected_phrases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "doc.md"
            doc.write_text("text", encoding="utf-8")
            csv_path = root / "questions.csv"
            csv_path.write_text("question,limit\nWhat is observer?,8\n", encoding="utf-8")
            dataset, problems, _warnings = build_dataset(
                course_name="Patterns",
                course_description="",
                questions_csv=csv_path,
                doc_paths=[str(doc)],
                doc_manifest="",
                chunk_size=900,
                default_limit=8,
                strict=True,
            )
            self.assertTrue(problems)
            self.assertEqual(dataset["queries"], [])


if __name__ == "__main__":
    unittest.main()
