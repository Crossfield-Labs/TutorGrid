from __future__ import annotations

import unittest

from backend.profile.service import LearningProfileService
from backend.scheduler.service import LearningPushScheduler
from backend.sessions.state import OrchestratorSessionState
from tests.temp_paths import workspace_temp_dir


class LearningPushSchedulerTests(unittest.TestCase):
    def test_generate_pushes_creates_record_for_completed_session(self) -> None:
        with workspace_temp_dir("push-") as temp_dir:
            path = temp_dir / "orchestrator.sqlite3"
            profile_service = LearningProfileService(path=path)
            scheduler = LearningPushScheduler(path=path)
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace="study-space",
                task="复习马拉车算法",
                goal="整理核心思路",
            )
            session.status = "COMPLETED"
            session.latest_summary = "已经梳理出镜像位置、中心和右边界的关系。"
            profiles = profile_service.refresh_profiles(
                session=session,
                history_items=[{"kind": "summary", "detail": "需要下一步用例题巩固。"}],
                reason="completed",
            )

            pushes = scheduler.generate_pushes(session=session, profiles=profiles, reason="completed")

            self.assertEqual(len(pushes), 1)
            self.assertEqual(pushes[0]["pushType"], "learning_followup")
            self.assertIn("trackedTopics", pushes[0]["payload"])
            stored = scheduler.list_pushes(session_id=session.session_id, limit=10)
            self.assertEqual(len(stored), 1)
            self.assertIn("recommendation", stored[0]["payload"])

    def test_generate_pushes_skips_non_completed_sessions(self) -> None:
        with workspace_temp_dir("push-") as temp_dir:
            path = temp_dir / "orchestrator.sqlite3"
            scheduler = LearningPushScheduler(path=path)
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace="study-space",
                task="复习马拉车算法",
                goal="整理核心思路",
            )

            pushes = scheduler.generate_pushes(session=session, profiles={}, reason="failed")

            self.assertEqual(pushes, [])


if __name__ == "__main__":
    unittest.main()
