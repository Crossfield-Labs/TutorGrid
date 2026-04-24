from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.knowledge.service import KnowledgeBaseService
from backend.knowledge.store import SQLiteKnowledgeStore
from backend.providers.base import LLMResponse
from backend.rag.service import RagService


class _StubProvider:
    async def chat(self, *, messages, tools=None):  # noqa: ANN001
        _ = tools
        prompt = str(messages[-1].get("content") or "")
        if "rewrite" in prompt.lower() or "3" in prompt:
            return LLMResponse(
                content=(
                    "observer pattern definition\n"
                    "publish subscribe workflow\n"
                    "one to many dependency"
                )
            )
        if "hyde" in prompt.lower() or "answer" in prompt.lower():
            return LLMResponse(content="Observer pattern keeps one-to-many dependency synchronized by notification.")
        return LLMResponse(content="")


class _NoopTracer:
    def start_run(self, **_: object) -> None:  # noqa: ANN003
        return None

    def end_run(self, run_id: str | None, **_: object) -> None:  # noqa: ANN003
        _ = run_id


class _HydeFailProvider:
    async def chat(self, *, messages, tools=None):  # noqa: ANN001
        _ = tools
        prompt = str(messages[-1].get("content") or "").lower()
        if "rewrite the question" in prompt:
            return LLMResponse(content="observer pattern overview\nobserver pattern examples")
        if "hypothetical answer" in prompt or "generate a direct answer" in prompt:
            raise RuntimeError("simulated hyde provider failure")
        if "answer the user question" in prompt:
            return LLMResponse(content="Observer pattern keeps subscribers updated when publisher state changes.")
        return LLMResponse(content="")


class RagServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_rag_query_returns_ranked_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            kb_service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            course = kb_service.create_course(name="Software Architecture", description="Chapter tests")

            source_file = temp_root / "observer.md"
            source_file.write_text(
                (
                    "Observer pattern defines one-to-many dependency between objects.\n"
                    "When subject state changes, observers are notified and updated.\n"
                    "This is a classic publish-subscribe model.\n"
                ),
                encoding="utf-8",
            )
            ingest = kb_service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")

            rag_service = RagService(knowledge_service=kb_service, llm_provider=_StubProvider())
            response = await rag_service.query(
                course_id=str(course["courseId"]),
                question="What is the core idea of observer pattern?",
                limit=3,
            )

            self.assertEqual(response["courseId"], course["courseId"])
            self.assertTrue(response["items"])
            self.assertLessEqual(len(response["items"]), 3)
            top = response["items"][0]
            self.assertTrue(any("Observer pattern" in item["content"] for item in response["items"]))
            self.assertIn("denseScore", top)
            self.assertIn("lexicalScore", top)
            self.assertIn("rerankScore", top)
            self.assertIn("multiQueries", response["debug"])
            self.assertIn("answer", response)
            self.assertTrue(str(response.get("answer") or "").strip())

    async def test_rag_query_works_with_noop_tracer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            kb_service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            course = kb_service.create_course(name="Distributed Systems", description="")

            source_file = temp_root / "consensus.md"
            source_file.write_text(
                (
                    "Raft keeps replicated logs consistent across nodes.\n"
                    "Leaders append entries and followers confirm by quorum.\n"
                ),
                encoding="utf-8",
            )
            ingest = kb_service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")

            rag_service = RagService(knowledge_service=kb_service, llm_provider=_StubProvider())
            rag_service.tracer = _NoopTracer()
            response = await rag_service.query(
                course_id=str(course["courseId"]),
                question="How does raft keep consistency?",
                limit=2,
            )
            self.assertTrue(response["items"])
            self.assertLessEqual(len(response["items"]), 2)

    async def test_hyde_falls_back_to_question_when_llm_call_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            db_path = temp_root / "orchestrator.sqlite3"
            store = SQLiteKnowledgeStore(db_path)
            kb_service = KnowledgeBaseService(store=store, root=temp_root / "knowledge_bases")
            course = kb_service.create_course(name="Patterns", description="")

            source_file = temp_root / "observer.md"
            source_file.write_text(
                "Observer pattern defines one-to-many dependency between objects.",
                encoding="utf-8",
            )
            ingest = kb_service.ingest_file(course_id=str(course["courseId"]), file_path=str(source_file))
            self.assertEqual(ingest["status"], "success")

            rag_service = RagService(knowledge_service=kb_service, llm_provider=_HydeFailProvider())
            response = await rag_service.query(
                course_id=str(course["courseId"]),
                question="Observer pattern 核心思想是什么？",
                limit=3,
            )
            debug = response.get("debug") or {}
            self.assertEqual(str(debug.get("hydeSource") or ""), "question_fallback")
            self.assertEqual(str(debug.get("hyde") or ""), "Observer pattern 核心思想是什么？")
            self.assertTrue(str(debug.get("hydeError") or "").strip())
            self.assertTrue(str(response.get("answer") or "").strip())


if __name__ == "__main__":
    unittest.main()
