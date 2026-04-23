from __future__ import annotations

from contextlib import closing
import sqlite3
import unittest
from pathlib import Path

from backend.sessions.state import OrchestratorSessionState
from backend.storage.sqlite_store import SQLiteSessionStore
from tests.temp_paths import workspace_temp_dir


class StorageTests(unittest.TestCase):
    def test_sqlite_store_persists_session_and_snapshot(self) -> None:
        with workspace_temp_dir("storage-") as temp_dir:
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
            self.assertEqual(store.get_session_snapshot(session.session_id)["task"], "inspect")

    def test_sqlite_store_persists_messages_errors_and_artifacts(self) -> None:
        with workspace_temp_dir("storage-") as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            store = SQLiteSessionStore(db_path)
            session = OrchestratorSessionState(
                task_id="task-2",
                node_id="node-2",
                runner="orchestrator",
                workspace=".",
                task="inspect",
                goal="inspect",
            )
            session.context["planner_messages"] = [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "done"},
            ]
            session.error = "boom"
            session.stop_reason = "failed"
            session.phase = "failed"
            session.active_worker = "codex"
            session.latest_artifact_summary = "生成了 1 个产物"
            session.artifacts.append("notes/output.md")
            session.worker_runs.append(
                {
                    "worker": "codex",
                    "artifacts": [
                        {"path": "notes/output.md", "change_type": "created", "size": 128},
                    ],
                }
            )

            store.save_session(session)

            messages = store.list_session_messages(session.session_id, limit=20)
            errors = store.list_session_errors(session.session_id, limit=20)
            artifacts = store.list_session_artifacts(session.session_id, limit=20)

            self.assertEqual(len(messages), 3)
            self.assertEqual(messages[1]["role"], "user")
            self.assertEqual(errors[0]["errorCode"], "failed")
            self.assertEqual(errors[0]["worker"], "codex")
            self.assertEqual(artifacts[0]["path"], "notes/output.md")
            self.assertEqual(artifacts[0]["changeType"], "created")


if __name__ == "__main__":
    unittest.main()

