from __future__ import annotations

import unittest

from backend.profile.service import LearningProfileService
from backend.sessions.state import OrchestratorSessionState
from tests.temp_paths import workspace_temp_dir


class LearningProfileServiceTests(unittest.TestCase):
    def test_refresh_profiles_persists_l1_l2_l3_l4(self) -> None:
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
            self.assertIn("L3", profiles)
            self.assertIn("L4", profiles)
            self.assertEqual(profiles["L1"]["profileKey"], session.session_id)
            self.assertTrue(profiles["L2"]["facts"])
            self.assertTrue(profiles["L3"]["summary"]["trackedTopics"])
            self.assertTrue(profiles["L4"]["summary"]["focusAreas"])

    def test_refresh_profiles_rolls_multiple_sessions_into_project_and_long_term_memory(self) -> None:
        with workspace_temp_dir("profile-") as temp_dir:
            service = LearningProfileService(path=temp_dir / "orchestrator.sqlite3")
            sessions = [
                ("讲解马拉车算法", "理解线性时间原理", "马拉车算法通过维护中心和右边界实现线性时间。"),
                ("复习 KMP 算法", "理解 next 数组", "KMP 通过前后缀复用减少回退。"),
            ]
            latest_profiles: dict[str, dict[str, object]] = {}
            for index, (task, goal, detail) in enumerate(sessions, start=1):
                session = OrchestratorSessionState(
                    task_id=f"task-{index}",
                    node_id=f"node-{index}",
                    runner="orchestrator",
                    workspace="study-space",
                    task=task,
                    goal=goal,
                )
                session.status = "COMPLETED"
                latest_profiles = service.refresh_profiles(
                    session=session,
                    history_items=[{"kind": "summary", "detail": detail}],
                    reason="completed",
                )

            self.assertIn("讲解马拉车算法", latest_profiles["L3"]["summary"]["trackedTopics"])
            self.assertIn("复习 KMP 算法", latest_profiles["L3"]["summary"]["trackedTopics"])
            self.assertTrue(latest_profiles["L4"]["summary"]["recurringTopics"])

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
