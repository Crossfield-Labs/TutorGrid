from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.profile.store import SQLiteLearningProfileStore
from backend.sessions.state import OrchestratorSessionState
from backend.storage.sqlite_store import SQLiteSessionStore
from backend.tools.database import query_database
from tests.temp_paths import workspace_temp_dir


class DatabaseToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_database_reads_supported_tables(self) -> None:
        with workspace_temp_dir("db-tool-") as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            session_store = SQLiteSessionStore(db_path)
            profile_store = SQLiteLearningProfileStore(db_path)

            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace="study-space",
                task="讲解马拉车算法",
                goal="理解原理",
            )
            session_store.save_session(session)
            profile_store.upsert_profile(
                profile_level="L4",
                profile_key="workspace-key",
                session_id=session.session_id,
                workspace=session.workspace,
                topic=session.task,
                summary={"focusAreas": ["马拉车算法"]},
                facts=[{"title": "马拉车算法", "value": 2, "category": "focus_area"}],
                metadata={"kind": "long_term"},
                created_at=session.created_at,
                updated_at=session.updated_at,
            )

            with patch("backend.tools.database.DatabaseInspector") as inspector_cls:
                inspector = inspector_cls.return_value
                from backend.db.inspector import DatabaseInspector as RealInspector

                real_inspector = RealInspector(db_path)
                inspector.query_json.side_effect = real_inspector.query_json

                sessions_json = await query_database("sessions", limit=5)
                profiles_json = await query_database("learning_profiles", profile_level="L4", limit=5)

            sessions = json.loads(sessions_json)
            profiles = json.loads(profiles_json)
            self.assertEqual(sessions[0]["task"], "讲解马拉车算法")
            self.assertEqual(profiles[0]["profileLevel"], "L4")


if __name__ == "__main__":
    unittest.main()
