from __future__ import annotations

from pathlib import Path
import unittest

from backend.sessions.state import OrchestratorSessionState
from backend.storage.jsonl_trace import JsonlTraceStore
from tests.temp_paths import workspace_temp_dir


class TraceHistoryTests(unittest.TestCase):
    def test_jsonl_trace_store_reads_session_history(self) -> None:
        with workspace_temp_dir("trace-") as temp_dir:
            store = JsonlTraceStore(temp_dir)
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

    def test_jsonl_trace_store_reads_raw_trace_entries(self) -> None:
        with workspace_temp_dir("trace-") as temp_dir:
            store = JsonlTraceStore(Path(temp_dir))
            session = OrchestratorSessionState(
                task_id="task-2",
                node_id="node-2",
                runner="pc_subagent",
                workspace=".",
                task="trace repo",
                goal="trace repo",
            )
            store.append_session_event(
                session,
                event="orchestrator.session.artifact.created",
                payload={"artifact": {"path": "notes/output.md"}},
            )

            items = store.list_session_trace(session.session_id, limit=20)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["event"], "orchestrator.session.artifact.created")
            self.assertEqual(items[0]["payload"]["artifact"]["path"], "notes/output.md")


if __name__ == "__main__":
    unittest.main()

