from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.memory.embedding import HashedTokenEmbedder
from backend.memory.service import MemoryService


class _NoopTracer:
    def start_run(self, **_: object) -> None:  # noqa: ANN003
        return None

    def end_run(self, run_id: str | None, **_: object) -> None:  # noqa: ANN003
        _ = run_id


class MemoryServiceTests(unittest.TestCase):
    def test_compact_session_filters_noise_and_persists_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ORCHESTRATOR_MEMORY_INDEX_BACKEND": "json"}, clear=False):
                service = MemoryService(path=Path(temp_dir) / "memory.sqlite3", embedder=HashedTokenEmbedder())
                result = service.compact_session(
                    session_id="session-1",
                    task="Explain Manacher algorithm",
                    goal="Describe core idea and time complexity",
                    history_items=[
                        {
                            "event": "orchestrator.session.subnode.started",
                            "kind": "substep",
                            "title": "working",
                            "detail": "running intermediate processing",
                        },
                        {
                            "event": "orchestrator.session.summary",
                            "kind": "summary",
                            "title": "summary",
                            "detail": "Manacher keeps center and right bound to amortize expansion to linear time.",
                        },
                        {
                            "event": "orchestrator.session.completed",
                            "kind": "summary",
                            "title": "completed",
                            "detail": "Final answer includes O(n) complexity.",
                        },
                    ],
                )

            self.assertEqual(result["sessionId"], "session-1")
            self.assertGreaterEqual(result["documentCount"], 2)
            self.assertEqual(result.get("indexBackend"), "json")
            results = service.search(query="linear time manacher algorithm", limit=3)
            self.assertTrue(results)
            self.assertEqual(results[0].session_id, "session-1")

    def test_memory_service_works_with_noop_tracer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MemoryService(path=Path(temp_dir) / "memory.sqlite3", embedder=HashedTokenEmbedder())
            service.tracer = _NoopTracer()
            compacted = service.compact_session(
                session_id="session-2",
                task="Explain observer pattern",
                goal="Summarize concept and examples",
                history_items=[
                    {
                        "event": "orchestrator.session.summary",
                        "kind": "summary",
                        "title": "summary",
                        "detail": "Observer pattern keeps subscribers updated on state changes.",
                    }
                ],
            )
            self.assertEqual(compacted["sessionId"], "session-2")
            results = service.search(query="observer subscribers", limit=2)
            self.assertTrue(results)

    def test_memory_search_respects_session_filter_with_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ORCHESTRATOR_MEMORY_INDEX_BACKEND": "json"}, clear=False):
                service = MemoryService(path=Path(temp_dir) / "memory.sqlite3", embedder=HashedTokenEmbedder())
                service.compact_session(
                    session_id="session-a",
                    task="Sorting",
                    goal="Explain merge sort",
                    history_items=[
                        {
                            "event": "orchestrator.session.summary",
                            "kind": "summary",
                            "title": "summary",
                            "detail": "Merge sort uses divide and conquer and stable merging.",
                        }
                    ],
                )
                service.compact_session(
                    session_id="session-b",
                    task="Graphs",
                    goal="Explain Dijkstra",
                    history_items=[
                        {
                            "event": "orchestrator.session.summary",
                            "kind": "summary",
                            "title": "summary",
                            "detail": "Dijkstra uses greedy relaxation on non-negative weights.",
                        }
                    ],
                )

                scoped = service.search(query="merge sort divide conquer", limit=5, session_id="session-a")
                self.assertTrue(scoped)
                self.assertTrue(all(item.session_id == "session-a" for item in scoped))

    def test_memory_reindex_returns_index_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ORCHESTRATOR_MEMORY_INDEX_BACKEND": "json"}, clear=False):
                service = MemoryService(path=Path(temp_dir) / "memory.sqlite3", embedder=HashedTokenEmbedder())
                service.compact_session(
                    session_id="session-r",
                    task="DP",
                    goal="Explain knapsack",
                    history_items=[
                        {
                            "event": "orchestrator.session.summary",
                            "kind": "summary",
                            "title": "summary",
                            "detail": "0-1 knapsack uses capacity-state dynamic programming.",
                        }
                    ],
                )
                payload = service.reindex()
                self.assertEqual(payload.get("indexBackend"), "json")
                self.assertGreater(int(payload.get("documentCount") or 0), 0)


if __name__ == "__main__":
    unittest.main()
