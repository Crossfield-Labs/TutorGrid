from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.knowledge.service import KnowledgeBaseService
from backend.knowledge.store import SQLiteKnowledgeStore
from backend.memory.embedding import HashedTokenEmbedder


class _NoopTracer:
    def start_run(self, **_: object) -> None:  # noqa: ANN003
        return None

    def end_run(self, run_id: str | None, **_: object) -> None:  # noqa: ANN003
        _ = run_id


class _DeterministicEmbedder:
    def embed_text(self, text: str) -> list[float]:
        normalized = str(text or "")
        return [float(len(normalized)), float(sum(ord(ch) for ch in normalized) % 997)]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class KnowledgeServiceTests(unittest.TestCase):
    def test_create_course_and_ingest_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")

            course = service.create_course(name="Software Architecture", description="Final review")
            source_file = temp_root / "chapter1.md"
            source_file.write_text(
                (
                    "# Observer Pattern\n"
                    "Observer pattern defines one-to-many dependency between objects.\n"
                    "A key mechanism is publish-subscribe.\n"
                ),
                encoding="utf-8",
            )

            result = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))

            self.assertEqual(result["status"], "success")
            self.assertGreater(result["chunkCount"], 0)

            files = service.list_files(course_id=str(course["courseId"]))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["parseStatus"], "success")

            chunks = service.list_chunks(course_id=str(course["courseId"]), limit=10)
            self.assertTrue(chunks)
            self.assertIn("Observer Pattern", chunks[0]["content"])

            job = service.get_job(job_id=str(result["jobId"]))
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "success")

    def test_ingest_pdf_copies_sidecar_and_preserves_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")

            course = service.create_course(name="Machine Learning", description="PDF sidecar regression")
            source_file = temp_root / "lecture.pdf"
            source_file.write_bytes(b"%PDF-1.4 fake")
            source_file.with_name("lecture.pdf.ocr.txt").write_text(
                "page 1\n"
                "Decision tree entropy and information gain are used to choose the best split. "
                "This sidecar text simulates OCR extracted from a scanned course slide.",
                encoding="utf-8",
            )

            result = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file), chunk_size=200)

            self.assertEqual(result["status"], "success")
            self.assertGreater(result["chunkCount"], 0)
            chunks = service.list_chunks_for_retrieval(course_id=str(course["courseId"]), limit=10)
            self.assertTrue(chunks)
            metadata = chunks[0]["metadata"]
            self.assertEqual(metadata.get("originalName"), "lecture.pdf")
            self.assertEqual(metadata.get("fileExt"), ".pdf")
            self.assertIn("Decision tree entropy", chunks[0]["content"])

    def test_list_jobs_returns_course_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")

            course = service.create_course(name="Computer Networks", description="")
            source_file = temp_root / "chapter_jobs.txt"
            source_file.write_text("TCP handshake and retransmission.", encoding="utf-8")
            ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")

            jobs = service.list_jobs(course_id=str(course["courseId"]), limit=20)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["jobId"], ingest["jobId"])
            self.assertEqual(jobs[0]["status"], "success")

    def test_ingest_requires_existing_course(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            store = SQLiteKnowledgeStore(temp_root / "orchestrator.sqlite3")
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            source_file = temp_root / "test.txt"
            source_file.write_text("hello world", encoding="utf-8")
            with self.assertRaises(ValueError):
                service.ingest_file(course_id="missing", file_path=str(source_file))

    def test_ingest_works_with_noop_tracer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            service.tracer = _NoopTracer()

            course = service.create_course(name="Distributed Systems", description="")
            source_file = temp_root / "chapter2.txt"
            source_file.write_text("Raft consensus basics.", encoding="utf-8")

            result = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(result["status"], "success")
            self.assertGreater(result["chunkCount"], 0)

    def test_delete_file_removes_records_and_staged_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            course = service.create_course(name="Data Structures", description="")
            source_file = temp_root / "chapter3.txt"
            source_file.write_text("Hash table collision handling.", encoding="utf-8")
            ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")
            files = service.list_files(course_id=str(course["courseId"]))
            self.assertEqual(len(files), 1)
            staged_path = Path(str(files[0]["storedPath"]))
            self.assertTrue(staged_path.exists())
            delete_result = service.delete_file(course_id=str(course["courseId"]), file_id=str(files[0]["fileId"]))
            self.assertTrue(delete_result["deleted"])
            self.assertFalse(staged_path.exists())
            self.assertFalse(service.list_files(course_id=str(course["courseId"])))
            self.assertFalse(service.list_chunks(course_id=str(course["courseId"])))

    def test_delete_course_removes_course_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            course = service.create_course(name="Operating Systems", description="")
            source_file = temp_root / "chapter4.txt"
            source_file.write_text("Process scheduling basics.", encoding="utf-8")
            ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")
            course_dir = temp_root / "knowledge_bases" / str(course["courseId"])
            self.assertTrue(course_dir.exists())
            deleted = service.delete_course(course_id=str(course["courseId"]))
            self.assertTrue(deleted["deleted"])
            self.assertFalse(course_dir.exists())
            remaining = service.list_courses()
            self.assertFalse(any(item["courseId"] == course["courseId"] for item in remaining))

    def test_reembed_course_updates_chunk_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            service = KnowledgeBaseService(
                store=store,
                root=temp_root / "knowledge_bases",
                embedder=HashedTokenEmbedder(dimensions=24),
            )
            course = service.create_course(name="Databases", description="")
            source_file = temp_root / "chapter5.txt"
            source_file.write_text("Normalization and transaction isolation.", encoding="utf-8")
            ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")

            service.embedder = _DeterministicEmbedder()
            result = service.reembed_course(course_id=str(course["courseId"]), batch_size=8)
            self.assertGreater(result["chunkCount"], 0)
            self.assertEqual(result["updatedCount"], result["chunkCount"])
            self.assertEqual(result["dimensions"], 2)

            chunks = service.list_chunks_for_retrieval(course_id=str(course["courseId"]))
            self.assertTrue(chunks)
            self.assertTrue(all(len(item.get("embedding") or []) == 2 for item in chunks))

    def test_search_chunk_scores_uses_persistent_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            with patch.dict(os.environ, {"ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND": "json"}, clear=False):
                store = SQLiteKnowledgeStore(db_path)
                service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
                course = service.create_course(name="AI Fundamentals", description="")
                source_file = temp_root / "chapter_index.txt"
                source_file.write_text(
                    "Transformer attention and positional encoding.\n"
                    "Convolutional neural networks for image tasks.\n",
                    encoding="utf-8",
                )
                ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
                self.assertEqual(ingest["status"], "success")
                self.assertEqual(ingest.get("indexBackend"), "json")

                scores = service.search_chunk_scores(
                    course_id=str(course["courseId"]),
                    queries=["How does attention work in transformer models?"],
                    limit=10,
                )
                self.assertTrue(scores)
                self.assertTrue(all(float(score) >= 0.0 for score in scores.values()))

    def test_reindex_course_returns_index_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            with patch.dict(os.environ, {"ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND": "json"}, clear=False):
                store = SQLiteKnowledgeStore(db_path)
                service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
                course = service.create_course(name="Compilers", description="")
                source_file = temp_root / "chapter_reindex.txt"
                source_file.write_text("LL parsing and LR parsing basics.", encoding="utf-8")
                ingest = service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
                self.assertEqual(ingest["status"], "success")

                payload = service.reindex_course(course_id=str(course["courseId"]))
                self.assertEqual(payload["courseId"], course["courseId"])
                self.assertEqual(payload["indexBackend"], "json")
                self.assertGreater(payload["chunkCount"], 0)


if __name__ == "__main__":
    unittest.main()
