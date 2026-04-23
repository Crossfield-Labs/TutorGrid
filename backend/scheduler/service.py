from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.profile.store import SQLiteLearningProfileStore
from backend.sessions.state import OrchestratorSessionState


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningPushScheduler:
    def __init__(self, path: Path | None = None) -> None:
        self.store = SQLiteLearningProfileStore(
            path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        )

    def generate_pushes(
        self,
        *,
        session: OrchestratorSessionState,
        profiles: dict[str, dict[str, Any]],
        reason: str,
    ) -> list[dict[str, Any]]:
        if reason != "completed":
            return []
        l2 = profiles.get("L2") or {}
        l4 = profiles.get("L4") or {}
        summary = (l2.get("summary") or {}).get("latestOutcome") or session.latest_summary or session.task
        focus_areas = (l4.get("summary") or {}).get("focusAreas") or []
        title = f"学习推进建议：{session.task[:32]}"
        message = summary[:160]
        payload = {
            "sessionId": session.session_id,
            "workspace": session.workspace,
            "task": session.task,
            "goal": session.goal,
            "focusAreas": focus_areas[:3],
            "profileKeys": {level: value.get("profileKey", "") for level, value in profiles.items()},
            "recommendation": self._build_recommendation(session=session, focus_areas=focus_areas),
        }
        record = self.store.create_push_record(
            session_id=session.session_id,
            profile_level="L4",
            profile_key=str(l4.get("profileKey") or ""),
            push_type="learning_followup",
            title=title,
            message=message,
            payload=payload,
            status="generated",
            created_at=_utcnow(),
        )
        return [
            {
                "pushId": record.push_id,
                "sessionId": record.session_id,
                "profileLevel": record.profile_level,
                "profileKey": record.profile_key,
                "pushType": record.push_type,
                "title": record.title,
                "message": record.message,
                "payload": record.payload,
                "status": record.status,
                "createdAt": record.created_at,
            }
        ]

    def list_pushes(self, *, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [
            {
                "pushId": record.push_id,
                "sessionId": record.session_id,
                "profileLevel": record.profile_level,
                "profileKey": record.profile_key,
                "pushType": record.push_type,
                "title": record.title,
                "message": record.message,
                "payload": record.payload,
                "status": record.status,
                "createdAt": record.created_at,
            }
            for record in self.store.list_push_records(session_id=session_id, limit=limit)
        ]

    def _build_recommendation(self, *, session: OrchestratorSessionState, focus_areas: list[str]) -> str:
        if focus_areas:
            return f"建议下一步围绕 {', '.join(focus_areas[:2])} 做一次针对性复盘或练习。"
        return f"建议围绕“{session.task[:24]}”继续补一轮例题或概念复盘。"
