from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore


class TraceHistoryTests(unittest.TestCase):
    def test_jsonl_trace_store_reads_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonlTraceStore(Path(temp_dir))
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="pc_subagent",
                workspace=".",
                task="inspect repo",
                goal="inspect repo",
            )
            store.append_session_event(
                session,
                event="orchestrator.session.phase",
                payload={"message": "planning", "phase": "planning"},
            )
            store.append_session_event(
                session,
                event="orchestrator.session.summary",
                payload={"message": "done"},
            )

            items = store.list_session_history(session.session_id, limit=20)

            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["kind"], "phase")
            self.assertEqual(items[1]["kind"], "summary")
            self.assertEqual(items[1]["detail"], "done")


if __name__ == "__main__":
    unittest.main()

