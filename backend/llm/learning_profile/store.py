from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _loads_list(raw: str) -> list[Any]:
    try:
        parsed = json.loads(raw or "[]")
    except Exception:
        return []
    if isinstance(parsed, list):
        return parsed
    return []


class SQLiteLearningProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_profile_l1_preferences (
                    user_id TEXT PRIMARY KEY,
                    preferences_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_profile_l2_course_contexts (
                    context_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, course_id)
                );

                CREATE TABLE IF NOT EXISTS learning_profile_l4_mastery_points (
                    point_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    knowledge_point TEXT NOT NULL,
                    mastery REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    last_practiced_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, course_id, knowledge_point)
                );

                CREATE INDEX IF NOT EXISTS idx_learning_profile_l2_user
                ON learning_profile_l2_course_contexts(user_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_learning_profile_l4_user_course
                ON learning_profile_l4_mastery_points(user_id, course_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_learning_profile_l4_user_mastery
                ON learning_profile_l4_mastery_points(user_id, mastery ASC, updated_at DESC);
                """
            )
            connection.commit()

    def get_l1_preferences(self, *, user_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT user_id, preferences_json, created_at, updated_at
                FROM learning_profile_l1_preferences
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return {
                "userId": user_id,
                "preferences": {},
                "createdAt": "",
                "updatedAt": "",
            }
        return {
            "userId": str(row["user_id"]),
            "preferences": _loads_object(str(row["preferences_json"])),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def upsert_l1_preferences(self, *, user_id: str, preferences: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT created_at FROM learning_profile_l1_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            created_at = str(row["created_at"]) if row is not None else now
            connection.execute(
                """
                INSERT INTO learning_profile_l1_preferences (
                    user_id, preferences_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    preferences_json=excluded.preferences_json,
                    updated_at=excluded.updated_at
                """,
                (user_id, json.dumps(preferences, ensure_ascii=False), created_at, now),
            )
            connection.commit()
        return {
            "userId": user_id,
            "preferences": dict(preferences),
            "createdAt": created_at,
            "updatedAt": now,
        }

    def list_l2_contexts(self, *, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT context_id, user_id, course_id, course_name, context_json, created_at, updated_at
                FROM learning_profile_l2_course_contexts
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, max(1, int(limit))),
            ).fetchall()
        return [
            {
                "contextId": str(row["context_id"]),
                "userId": str(row["user_id"]),
                "courseId": str(row["course_id"]),
                "courseName": str(row["course_name"]),
                "context": _loads_object(str(row["context_json"])),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def upsert_l2_context(
        self,
        *,
        user_id: str,
        course_id: str,
        course_name: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        now = _utcnow()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT context_id, created_at
                FROM learning_profile_l2_course_contexts
                WHERE user_id = ? AND course_id = ?
                """,
                (user_id, course_id),
            ).fetchone()
            context_id = str(row["context_id"]) if row is not None else uuid4().hex
            created_at = str(row["created_at"]) if row is not None else now
            connection.execute(
                """
                INSERT INTO learning_profile_l2_course_contexts (
                    context_id, user_id, course_id, course_name, context_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, course_id) DO UPDATE SET
                    course_name=excluded.course_name,
                    context_json=excluded.context_json,
                    updated_at=excluded.updated_at
                """,
                (
                    context_id,
                    user_id,
                    course_id,
                    course_name,
                    json.dumps(context, ensure_ascii=False),
                    created_at,
                    now,
                ),
            )
            connection.commit()
        return {
            "contextId": context_id,
            "userId": user_id,
            "courseId": course_id,
            "courseName": course_name,
            "context": dict(context),
            "createdAt": created_at,
            "updatedAt": now,
        }

    def list_l4_points(
        self,
        *,
        user_id: str,
        course_id: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        normalized_course = course_id.strip()
        with closing(self._connect()) as connection:
            if normalized_course:
                rows = connection.execute(
                    """
                    SELECT
                        point_id, user_id, course_id, knowledge_point, mastery, confidence,
                        evidence_json, last_practiced_at, metadata_json, created_at, updated_at
                    FROM learning_profile_l4_mastery_points
                    WHERE user_id = ? AND course_id = ?
                    ORDER BY updated_at DESC, mastery ASC
                    LIMIT ?
                    """,
                    (user_id, normalized_course, max(1, int(limit))),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        point_id, user_id, course_id, knowledge_point, mastery, confidence,
                        evidence_json, last_practiced_at, metadata_json, created_at, updated_at
                    FROM learning_profile_l4_mastery_points
                    WHERE user_id = ?
                    ORDER BY updated_at DESC, mastery ASC
                    LIMIT ?
                    """,
                    (user_id, max(1, int(limit))),
                ).fetchall()
        return [self._row_to_l4_point(row) for row in rows]

    def list_l4_weak_points(
        self,
        *,
        user_id: str,
        threshold: float = 0.6,
        course_id: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_course = course_id.strip()
        with closing(self._connect()) as connection:
            if normalized_course:
                rows = connection.execute(
                    """
                    SELECT
                        point_id, user_id, course_id, knowledge_point, mastery, confidence,
                        evidence_json, last_practiced_at, metadata_json, created_at, updated_at
                    FROM learning_profile_l4_mastery_points
                    WHERE user_id = ? AND course_id = ? AND mastery <= ?
                    ORDER BY mastery ASC, updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, normalized_course, float(threshold), max(1, int(limit))),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        point_id, user_id, course_id, knowledge_point, mastery, confidence,
                        evidence_json, last_practiced_at, metadata_json, created_at, updated_at
                    FROM learning_profile_l4_mastery_points
                    WHERE user_id = ? AND mastery <= ?
                    ORDER BY mastery ASC, updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, float(threshold), max(1, int(limit))),
                ).fetchall()
        return [self._row_to_l4_point(row) for row in rows]

    def upsert_l4_point(
        self,
        *,
        user_id: str,
        course_id: str,
        knowledge_point: str,
        mastery: float,
        confidence: float,
        evidence: list[str],
        last_practiced_at: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = _utcnow()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT point_id, created_at
                FROM learning_profile_l4_mastery_points
                WHERE user_id = ? AND course_id = ? AND knowledge_point = ?
                """,
                (user_id, course_id, knowledge_point),
            ).fetchone()
            point_id = str(row["point_id"]) if row is not None else uuid4().hex
            created_at = str(row["created_at"]) if row is not None else now
            connection.execute(
                """
                INSERT INTO learning_profile_l4_mastery_points (
                    point_id, user_id, course_id, knowledge_point, mastery, confidence,
                    evidence_json, last_practiced_at, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, course_id, knowledge_point) DO UPDATE SET
                    mastery=excluded.mastery,
                    confidence=excluded.confidence,
                    evidence_json=excluded.evidence_json,
                    last_practiced_at=excluded.last_practiced_at,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    point_id,
                    user_id,
                    course_id,
                    knowledge_point,
                    float(mastery),
                    float(confidence),
                    json.dumps(evidence, ensure_ascii=False),
                    last_practiced_at,
                    json.dumps(metadata, ensure_ascii=False),
                    created_at,
                    now,
                ),
            )
            connection.commit()
        return {
            "pointId": point_id,
            "userId": user_id,
            "courseId": course_id,
            "knowledgePoint": knowledge_point,
            "mastery": float(mastery),
            "confidence": float(confidence),
            "evidence": list(evidence),
            "lastPracticedAt": last_practiced_at,
            "metadata": dict(metadata),
            "createdAt": created_at,
            "updatedAt": now,
        }

    @staticmethod
    def _row_to_l4_point(row: sqlite3.Row) -> dict[str, Any]:
        evidence = [str(item) for item in _loads_list(str(row["evidence_json"])) if str(item).strip()]
        return {
            "pointId": str(row["point_id"]),
            "userId": str(row["user_id"]),
            "courseId": str(row["course_id"]),
            "knowledgePoint": str(row["knowledge_point"]),
            "mastery": float(row["mastery"] or 0.0),
            "confidence": float(row["confidence"] or 0.0),
            "evidence": evidence,
            "lastPracticedAt": str(row["last_practiced_at"]),
            "metadata": _loads_object(str(row["metadata_json"])),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }
