from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
import re
from typing import Any

from backend.profile.store import LearningProfileRecord, SQLiteLearningProfileStore
from backend.sessions.state import OrchestratorSessionState


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_topic(*parts: str) -> str:
    text = " ".join(part.strip() for part in parts if part.strip())
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:160]


def _topic_key(text: str) -> str:
    if not text:
        return "empty"
    return sha1(text.encode("utf-8")).hexdigest()[:16]


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{3,}", lowered)
    stop = {"session", "summary", "completed", "failed", "task", "goal", "当前步骤", "正在处理中"}
    return [word for word in words if word not in stop]


class LearningProfileService:
    def __init__(self, path: Path | None = None) -> None:
        self.store = SQLiteLearningProfileStore(
            path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        )

    def refresh_profiles(
        self,
        *,
        session: OrchestratorSessionState,
        history_items: list[dict[str, Any]],
        reason: str,
    ) -> dict[str, dict[str, Any]]:
        snapshot = session.build_snapshot()
        topic = _normalize_topic(session.task, session.goal, snapshot.get("latestSummary", ""))
        evidence = self._build_evidence(history_items)
        updated_at = _utcnow()

        l1_summary = {
            "task": session.task,
            "goal": session.goal,
            "status": session.status,
            "phase": session.phase,
            "stopReason": session.stop_reason,
            "latestSummary": snapshot.get("latestSummary", ""),
            "reason": reason,
        }
        l1_facts = evidence["facts"][:8]
        self.store.upsert_profile(
            profile_level="L1",
            profile_key=session.session_id,
            session_id=session.session_id,
            workspace=session.workspace,
            topic=topic or session.task,
            summary=l1_summary,
            facts=l1_facts,
            metadata={"kind": "session", "keywords": evidence["keywords"][:10]},
            created_at=session.created_at,
            updated_at=updated_at,
        )

        l2_key = _topic_key(f"{session.workspace}::{topic or session.task}")
        l2_summary = {
            "topic": topic or session.task,
            "workspace": session.workspace,
            "latestSessionId": session.session_id,
            "latestStatus": session.status,
            "latestOutcome": snapshot.get("latestSummary", ""),
            "reason": reason,
        }
        l2_facts = evidence["facts"][:12]
        self.store.upsert_profile(
            profile_level="L2",
            profile_key=l2_key,
            session_id=session.session_id,
            workspace=session.workspace,
            topic=topic or session.task,
            summary=l2_summary,
            facts=l2_facts,
            metadata={"kind": "task", "keywords": evidence["keywords"][:12]},
            created_at=session.created_at,
            updated_at=updated_at,
        )

        l4_key = _topic_key(session.workspace or "global")
        existing_l4 = self.store.get_profile(profile_level="L4", profile_key=l4_key)
        long_term_facts = self._merge_long_term_facts(existing_l4, l2_facts, evidence["keywords"])
        l4_summary = {
            "workspace": session.workspace,
            "focusAreas": [fact["title"] for fact in long_term_facts[:5]],
            "lastSessionId": session.session_id,
            "lastUpdatedReason": reason,
        }
        self.store.upsert_profile(
            profile_level="L4",
            profile_key=l4_key,
            session_id=session.session_id,
            workspace=session.workspace,
            topic=topic or session.task,
            summary=l4_summary,
            facts=long_term_facts,
            metadata={"kind": "long_term", "keywords": evidence["keywords"][:20]},
            created_at=existing_l4.created_at if existing_l4 is not None else session.created_at,
            updated_at=updated_at,
        )

        return {
            "L1": self._record_payload(self.store.get_profile(profile_level="L1", profile_key=session.session_id)),
            "L2": self._record_payload(self.store.get_profile(profile_level="L2", profile_key=l2_key)),
            "L4": self._record_payload(self.store.get_profile(profile_level="L4", profile_key=l4_key)),
        }

    def get_profile(self, *, profile_level: str, profile_key: str) -> dict[str, Any] | None:
        record = self.store.get_profile(profile_level=profile_level, profile_key=profile_key)
        if record is None:
            return None
        return self._record_payload(record)

    def list_profiles(self, *, profile_level: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [self._record_payload(record) for record in self.store.list_profiles(profile_level=profile_level, limit=limit)]

    def list_push_records(self, *, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.store.list_push_records(session_id=session_id, limit=limit)]

    def _record_payload(self, record: LearningProfileRecord | None) -> dict[str, Any]:
        if record is None:
            return {}
        return {
            "profileLevel": record.profile_level,
            "profileKey": record.profile_key,
            "sessionId": record.session_id,
            "workspace": record.workspace,
            "topic": record.topic,
            "summary": record.summary,
            "facts": record.facts,
            "metadata": record.metadata,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
        }

    def _build_evidence(self, history_items: list[dict[str, Any]]) -> dict[str, Any]:
        details: list[str] = []
        for item in history_items:
            kind = str(item.get("kind") or "").strip()
            if kind in {"substep", "snapshot", "phase"}:
                continue
            detail = str(item.get("detail") or item.get("title") or "").strip()
            if detail:
                details.append(detail)
        joined = "\n".join(details[:20])
        keywords = Counter(_tokenize(joined))
        facts: list[dict[str, Any]] = []
        for keyword, count in keywords.most_common(10):
            facts.append(
                {
                    "title": keyword,
                    "value": count,
                    "category": "keyword",
                }
            )
        if joined:
            facts.insert(
                0,
                {
                    "title": "latest_outcome",
                    "value": details[-1][:240],
                    "category": "summary",
                },
            )
        return {
            "facts": facts,
            "keywords": [keyword for keyword, _ in keywords.most_common(20)],
        }

    def _merge_long_term_facts(
        self,
        existing: LearningProfileRecord | None,
        new_facts: list[dict[str, Any]],
        keywords: list[str],
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in (existing.facts if existing is not None else []):
            title = str(item.get("title") or "").strip()
            if title:
                merged[title] = dict(item)
        for item in new_facts:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            current = merged.get(title)
            if current is None:
                merged[title] = dict(item)
                continue
            if isinstance(item.get("value"), int) and isinstance(current.get("value"), int):
                current["value"] = int(current["value"]) + int(item["value"])
            else:
                current["value"] = item.get("value") or current.get("value")
        for keyword in keywords[:6]:
            merged.setdefault(
                keyword,
                {"title": keyword, "value": 1, "category": "focus_area"},
            )
        values = list(merged.values())
        values.sort(key=lambda item: (0 if item.get("category") == "summary" else 1, -int(item.get("value", 1)) if isinstance(item.get("value"), int) else 0))
        return values[:16]
