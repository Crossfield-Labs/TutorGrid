from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.sessions.manager import SessionManager
from backend.storage.sqlite_store import SQLiteSessionStore


class SessionListTests(unittest.TestCase):
    def test_session_manager_lists_recent_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteSessionStore(Path(temp_dir) / "orchestrator.sqlite3")
            manager = SessionManager(store=store)
            first = manager.create(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace=".",
                task="first task",
                goal="first task",
            )
            second = manager.create(
                task_id="task-2",
                node_id="node-2",
                runner="pc_subagent",
                workspace=".",
                task="second task",
                goal="second task",
            )

            items = manager.list_sessions(limit=10)

            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["sessionId"], second.session_id)
            self.assertEqual(items[1]["sessionId"], first.session_id)
            self.assertEqual(items[0]["task"], "second task")


if __name__ == "__main__":
    unittest.main()

