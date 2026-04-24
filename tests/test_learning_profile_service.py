from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.learning_profile.service import LearningProfileService
from backend.learning_profile.store import SQLiteLearningProfileStore


class LearningProfileServiceTests(unittest.TestCase):
    def test_upsert_l1_l2_l4_and_build_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            store = SQLiteLearningProfileStore(db_path)
            service = LearningProfileService(store=store)

            l1 = service.upsert_l1_preferences(
                user_id="student-a",
                preferences={"outputStyle": "concise", "explainStyle": "step_by_step"},
            )
            self.assertEqual(l1["userId"], "student-a")
            self.assertEqual(l1["preferences"]["outputStyle"], "concise")

            l2 = service.upsert_l2_context(
                user_id="student-a",
                course_id="se-101",
                course_name="Software Engineering",
                context={
                    "activeExperiments": ["observer-lab", "api-design-lab"],
                    "fuzzyTopics": ["distributed transaction"],
                },
            )
            self.assertEqual(l2["courseId"], "se-101")
            self.assertEqual(l2["courseName"], "Software Engineering")

            low_mastery = service.upsert_l4_mastery(
                user_id="student-a",
                course_id="se-101",
                knowledge_point="observer pattern",
                mastery=0.38,
                confidence=0.82,
                evidence=["quiz-1 wrong"],
                metadata={"source": "quiz"},
            )
            high_mastery = service.upsert_l4_mastery(
                user_id="student-a",
                course_id="se-101",
                knowledge_point="uml sequence diagram",
                mastery=0.91,
                confidence=0.77,
                evidence=["lab complete"],
                metadata={"source": "lab"},
            )
            self.assertEqual(low_mastery["masteryBand"], "low")
            self.assertEqual(high_mastery["masteryBand"], "high")

            summary = service.get_profile(user_id="student-a", layer="summary", course_id="se-101", limit=50)
            self.assertEqual(summary["userId"], "student-a")
            self.assertEqual(summary["stats"]["courseCount"], 1)
            self.assertEqual(summary["stats"]["masteryPointCount"], 2)
            self.assertGreater(summary["l4"]["averageMastery"], 0.0)
            weak_points = summary["l4"]["weakPoints"]
            self.assertEqual(len(weak_points), 1)
            self.assertEqual(weak_points[0]["knowledgePoint"], "observer pattern")

    def test_l4_upsert_clamps_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            service = LearningProfileService(store=SQLiteLearningProfileStore(db_path))

            payload = service.upsert_l4_mastery(
                user_id="student-b",
                course_id="os-201",
                knowledge_point="process scheduling",
                mastery=2.0,
                confidence=-3.0,
            )

            self.assertAlmostEqual(payload["mastery"], 1.0)
            self.assertAlmostEqual(payload["confidence"], 0.0)
            self.assertEqual(payload["masteryBand"], "high")

    def test_l4_requires_course_and_knowledge_point(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "orchestrator.sqlite3"
            service = LearningProfileService(store=SQLiteLearningProfileStore(db_path))

            with self.assertRaises(ValueError):
                service.upsert_l4_mastery(
                    user_id="student-c",
                    course_id="",
                    knowledge_point="memory hierarchy",
                    mastery=0.4,
                )
            with self.assertRaises(ValueError):
                service.upsert_l4_mastery(
                    user_id="student-c",
                    course_id="ca-301",
                    knowledge_point="",
                    mastery=0.4,
                )


if __name__ == "__main__":
    unittest.main()
