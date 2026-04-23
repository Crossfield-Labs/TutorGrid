from __future__ import annotations

import unittest

from backend.profile.service import LearningProfileService
from backend.sessions.state import OrchestratorSessionState
from tests.temp_paths import workspace_temp_dir


class LearningProfileServiceTests(unittest.TestCase):
    def test_refresh_profiles_persists_l1_l2_l4(self) -> None:
        with workspace_temp_dir("profile-") as temp_dir:
            service = LearningProfileService(path=temp_dir / "orchestrator.sqlite3")
            session = OrchestratorSessionState(
                task_id="task-1",
                node_id="node-1",
                runner="orchestrator",
                workspace="study-space",
                task="讲解马拉车算法",
                goal="理解线性时间原理",
            )
            session.status = "COMPLETED"
            session.phase = "completed"
            session.latest_summary = "马拉车算法通过复用回文半径信息把扩展均摊为 O(n)。"

            profiles = service.refresh_profiles(
                session=session,
                history_items=[
                    {"kind": "summary", "detail": "马拉车算法通过维护中心和最右边界实现线性时间。"},
                    {"kind": "summary", "detail": "需要重点理解镜像位置和边界复用。"},
                ],
                reason="completed",
            )

            self.assertIn("L1", profiles)
            self.assertIn("L2", profiles)
            self.assertIn("L4", profiles)
            self.assertEqual(profiles["L1"]["profileKey"], session.session_id)
            self.assertTrue(profiles["L2"]["facts"])
            self.assertTrue(profiles["L4"]["summary"]["focusAreas"])

    def test_list_profiles_returns_recent_records(self) -> None:
        with workspace_temp_dir("profile-") as temp_dir:
            service = LearningProfileService(path=temp_dir / "orchestrator.sqlite3")
            for index in range(2):
                session = OrchestratorSessionState(
                    task_id=f"task-{index}",
                    node_id=f"node-{index}",
                    runner="orchestrator",
                    workspace="study-space",
                    task=f"任务 {index}",
                    goal=f"目标 {index}",
                )
                service.refresh_profiles(
                    session=session,
                    history_items=[{"kind": "summary", "detail": f"总结 {index}"}],
                    reason="completed",
                )

            items = service.list_profiles(profile_level="L2", limit=10)
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["profileLevel"], "L2")


if __name__ == "__main__":
    unittest.main()
