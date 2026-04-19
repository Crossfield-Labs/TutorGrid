from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sessions.state import OrchestratorSessionState
from storage.sqlite_store import SQLiteSessionStore


class StorageTests(unittest.TestCase):
    def test_sqlite_store_persists_session_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            store = SQLiteSessionStore(db_path)
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace=".",
                task="inspect",
                goal="inspect",
            )
            session.set_latest_summary("done")
            store.save_session(session)
            store.save_snapshot(session)

            with closing(sqlite3.connect(db_path)) as connection:
                session_row = connection.execute(
                    "SELECT latest_summary, status FROM sessions WHERE session_id = ?",
                    (session.session_id,),
                ).fetchone()
                snapshot_row = connection.execute(
                    "SELECT snapshot_version FROM session_snapshots WHERE session_id = ?",
                    (session.session_id,),
                ).fetchone()

            self.assertEqual(session_row[0], "done")
            self.assertEqual(session_row[1], "PENDING")
            self.assertEqual(snapshot_row[0], session.snapshot_version)


if __name__ == "__main__":
    unittest.main()
