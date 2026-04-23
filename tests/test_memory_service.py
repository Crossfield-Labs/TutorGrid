from __future__ import annotations

import unittest
from pathlib import Path

from backend.memory.service import MemoryService
from tests.temp_paths import workspace_temp_dir


class MemoryServiceTests(unittest.TestCase):
    def test_compact_session_filters_noise_and_persists_documents(self) -> None:
        with workspace_temp_dir("memory-") as temp_dir:
            service = MemoryService(path=Path(temp_dir) / "memory.sqlite3")
            result = service.compact_session(
                session_id="session-1",
                task="讲解马拉车算法",
                goal="解释原理和时间复杂度",
                history_items=[
                    {
                        "event": "orchestrator.session.subnode.started",
                        "kind": "substep",
                        "title": "正在处理当前步骤",
                        "detail": "正在执行必要的中间处理。",
                    },
                    {
                        "event": "orchestrator.session.summary",
                        "kind": "summary",
                        "title": "summary",
                        "detail": "马拉车算法通过维护中心和右边界，把回文扩展均摊到线性时间。",
                    },
                    {
                        "event": "orchestrator.session.completed",
                        "kind": "summary",
                        "title": "completed",
                        "detail": "最终回答已经生成，并包含时间复杂度 O(n)。",
                    },
                ],
            )

            self.assertEqual(result["sessionId"], "session-1")
            self.assertGreaterEqual(result["documentCount"], 2)
            results = service.search(query="线性时间的马拉车算法", limit=3)
            self.assertTrue(results)
            self.assertEqual(results[0].session_id, "session-1")


if __name__ == "__main__":
    unittest.main()
