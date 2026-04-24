from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from backend.dev.validate_rag_dataset import validate_dataset


class ValidateRagDatasetTests(unittest.TestCase):
    def test_validate_dataset_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc_path = root / "doc.txt"
            doc_path.write_text("hello", encoding="utf-8")
            dataset = {
                "documents": [{"path": "doc.txt", "chunkSize": 900}],
                "queries": [{"question": "q1", "expectedPhrases": ["hello"], "limit": 5}],
            }
            dataset_path = root / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            result = validate_dataset(dataset_path, strict=True)
            self.assertTrue(result["ok"])
            self.assertFalse(result["problems"])

    def test_validate_dataset_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = {
                "documents": [{"path": "missing.txt"}],
                "queries": [{"question": "q1"}],
            }
            dataset_path = root / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            result = validate_dataset(dataset_path, strict=False)
            self.assertFalse(result["ok"])
            self.assertTrue(any("file not found" in item for item in result["problems"]))


if __name__ == "__main__":
    unittest.main()
