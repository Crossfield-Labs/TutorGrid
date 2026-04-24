from __future__ import annotations

from pathlib import Path
from statistics import fmean
from typing import Any

from backend.learning_profile.store import SQLiteLearningProfileStore
from backend.observability import get_langsmith_tracer


def _normalize_user_id(raw_user_id: str) -> str:
    normalized = str(raw_user_id or "").strip()
    return normalized or "default"


def _clamp(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


class LearningProfileService:
    def __init__(
        self,
        *,
        store: SQLiteLearningProfileStore | None = None,
        path: Path | None = None,
    ) -> None:
        db_path = path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        self.store = store or SQLiteLearningProfileStore(db_path)
        self.tracer = get_langsmith_tracer()

    def get_profile(
        self,
        *,
        user_id: str = "default",
        layer: str = "summary",
        course_id: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        normalized_layer = str(layer or "").strip().lower() or "summary"
        normalized_course = str(course_id or "").strip()
        normalized_limit = max(1, int(limit))

        if normalized_layer == "l1":
            return self.store.get_l1_preferences(user_id=normalized_user)
        if normalized_layer == "l2":
            return {
                "userId": normalized_user,
                "items": self.store.list_l2_contexts(user_id=normalized_user, limit=normalized_limit),
            }
        if normalized_layer == "l4":
            return {
                "userId": normalized_user,
                "courseId": normalized_course,
                "items": self.store.list_l4_points(
                    user_id=normalized_user,
                    course_id=normalized_course,
                    limit=normalized_limit,
                ),
            }
        return self.get_profile_summary(user_id=normalized_user, course_id=normalized_course, limit=normalized_limit)

    def get_profile_summary(self, *, user_id: str = "default", course_id: str = "", limit: int = 100) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        normalized_course = str(course_id or "").strip()
        normalized_limit = max(1, int(limit))
        l1 = self.store.get_l1_preferences(user_id=normalized_user)
        l2_items = self.store.list_l2_contexts(user_id=normalized_user, limit=min(normalized_limit, 200))
        l4_items = self.store.list_l4_points(
            user_id=normalized_user,
            course_id=normalized_course,
            limit=min(normalized_limit, 300),
        )
        weak_points = self.store.list_l4_weak_points(
            user_id=normalized_user,
            course_id=normalized_course,
            threshold=0.6,
            limit=min(normalized_limit, 50),
        )
        average_mastery = fmean([float(item.get("mastery") or 0.0) for item in l4_items]) if l4_items else 0.0
        return {
            "userId": normalized_user,
            "l1": l1,
            "l2": {"items": l2_items},
            "l4": {
                "items": l4_items,
                "weakPoints": weak_points,
                "averageMastery": round(float(average_mastery), 4),
            },
            "stats": {
                "courseCount": len(l2_items),
                "masteryPointCount": len(l4_items),
                "weakPointCount": len(weak_points),
            },
        }

    def upsert_l1_preferences(self, *, user_id: str = "default", preferences: dict[str, Any]) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        if not isinstance(preferences, dict):
            raise ValueError("profileData must be an object for L1 preferences.")
        run_id = self.tracer.start_run(
            name="learning_profile.l1.upsert",
            run_type="chain",
            inputs={"userId": normalized_user, "keys": sorted(preferences.keys())},
            metadata={"module": "learning_profile", "layer": "l1"},
            tags=["learning_profile", "l1", "upsert"],
        )
        try:
            payload = self.store.upsert_l1_preferences(user_id=normalized_user, preferences=preferences)
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "learning_profile", "layer": "l1"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"userId": normalized_user},
                error=(str(exc).strip() or "upsert l1 failed")[:1200],
                metadata={"module": "learning_profile", "layer": "l1"},
                tags=["error"],
            )
            raise

    def list_l2_contexts(self, *, user_id: str = "default", limit: int = 100) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        items = self.store.list_l2_contexts(user_id=normalized_user, limit=max(1, int(limit)))
        return {"userId": normalized_user, "items": items}

    def upsert_l2_context(
        self,
        *,
        user_id: str = "default",
        course_id: str,
        course_name: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        normalized_course_id = str(course_id or "").strip()
        if not normalized_course_id:
            raise ValueError("courseId cannot be empty.")
        normalized_context = dict(context or {})
        normalized_course_name = str(course_name or "").strip() or str(
            normalized_context.get("courseName") or normalized_course_id
        )
        run_id = self.tracer.start_run(
            name="learning_profile.l2.upsert",
            run_type="chain",
            inputs={
                "userId": normalized_user,
                "courseId": normalized_course_id,
                "courseName": normalized_course_name,
                "contextKeys": sorted(normalized_context.keys()),
            },
            metadata={"module": "learning_profile", "layer": "l2"},
            tags=["learning_profile", "l2", "upsert"],
        )
        try:
            payload = self.store.upsert_l2_context(
                user_id=normalized_user,
                course_id=normalized_course_id,
                course_name=normalized_course_name,
                context=normalized_context,
            )
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "learning_profile", "layer": "l2"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"userId": normalized_user, "courseId": normalized_course_id},
                error=(str(exc).strip() or "upsert l2 failed")[:1200],
                metadata={"module": "learning_profile", "layer": "l2"},
                tags=["error"],
            )
            raise

    def list_l4_mastery(
        self,
        *,
        user_id: str = "default",
        course_id: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        normalized_course = str(course_id or "").strip()
        items = self.store.list_l4_points(user_id=normalized_user, course_id=normalized_course, limit=max(1, int(limit)))
        return {"userId": normalized_user, "courseId": normalized_course, "items": items}

    def upsert_l4_mastery(
        self,
        *,
        user_id: str = "default",
        course_id: str,
        knowledge_point: str,
        mastery: float,
        confidence: float = 0.5,
        evidence: list[str] | None = None,
        last_practiced_at: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_user = _normalize_user_id(user_id)
        normalized_course = str(course_id or "").strip()
        normalized_point = str(knowledge_point or "").strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if not normalized_point:
            raise ValueError("knowledgePoint cannot be empty.")
        normalized_mastery = _clamp(float(mastery), lower=0.0, upper=1.0)
        normalized_confidence = _clamp(float(confidence), lower=0.0, upper=1.0)
        normalized_evidence = [str(item).strip() for item in (evidence or []) if str(item).strip()]
        normalized_metadata = dict(metadata or {})
        normalized_last_practiced = str(last_practiced_at or "").strip()
        run_id = self.tracer.start_run(
            name="learning_profile.l4.upsert",
            run_type="chain",
            inputs={
                "userId": normalized_user,
                "courseId": normalized_course,
                "knowledgePoint": normalized_point,
                "mastery": normalized_mastery,
                "confidence": normalized_confidence,
                "evidenceCount": len(normalized_evidence),
            },
            metadata={"module": "learning_profile", "layer": "l4"},
            tags=["learning_profile", "l4", "upsert"],
        )
        try:
            payload = self.store.upsert_l4_point(
                user_id=normalized_user,
                course_id=normalized_course,
                knowledge_point=normalized_point,
                mastery=normalized_mastery,
                confidence=normalized_confidence,
                evidence=normalized_evidence,
                last_practiced_at=normalized_last_practiced,
                metadata=normalized_metadata,
            )
            payload["masteryBand"] = self._mastery_band(normalized_mastery)
            self.tracer.end_run(run_id, outputs=payload, metadata={"module": "learning_profile", "layer": "l4"})
            return payload
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"userId": normalized_user, "courseId": normalized_course, "knowledgePoint": normalized_point},
                error=(str(exc).strip() or "upsert l4 failed")[:1200],
                metadata={"module": "learning_profile", "layer": "l4"},
                tags=["error"],
            )
            raise

    @staticmethod
    def _mastery_band(mastery: float) -> str:
        if mastery >= 0.8:
            return "high"
        if mastery >= 0.5:
            return "medium"
        return "low"
