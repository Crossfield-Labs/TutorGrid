from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LearningProfileRecord:
    profile_level: str
    profile_key: str
    session_id: str
    workspace: str
    topic: str
    summary: dict[str, Any]
    facts: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class PushRecord:
    push_id: int
    session_id: str
    profile_level: str
    profile_key: str
    push_type: str
    title: str
    message: str
    payload: dict[str, Any]
    status: str
    created_at: str


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
                CREATE TABLE IF NOT EXISTS learning_profiles (
                    profile_level TEXT NOT NULL,
                    profile_key TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile_level, profile_key)
                );

                CREATE TABLE IF NOT EXISTS learning_push_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    profile_level TEXT NOT NULL,
                    profile_key TEXT NOT NULL,
                    push_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.commit()

    def upsert_profile(
        self,
        *,
        profile_level: str,
        profile_key: str,
        session_id: str,
        workspace: str,
        topic: str,
        summary: dict[str, Any],
        facts: list[dict[str, Any]],
        metadata: dict[str, Any],
        created_at: str,
        updated_at: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO learning_profiles (
                    profile_level, profile_key, session_id, workspace, topic,
                    summary_json, facts_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_level, profile_key) DO UPDATE SET
                    session_id=excluded.session_id,
                    workspace=excluded.workspace,
                    topic=excluded.topic,
                    summary_json=excluded.summary_json,
                    facts_json=excluded.facts_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    profile_level,
                    profile_key,
                    session_id,
                    workspace,
                    topic,
                    json.dumps(summary, ensure_ascii=False),
                    json.dumps(facts, ensure_ascii=False),
                    json.dumps(metadata, ensure_ascii=False),
                    created_at,
                    updated_at,
                ),
            )
            connection.commit()

    def get_profile(self, *, profile_level: str, profile_key: str) -> LearningProfileRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT profile_level, profile_key, session_id, workspace, topic,
                       summary_json, facts_json, metadata_json, created_at, updated_at
                FROM learning_profiles
                WHERE profile_level = ? AND profile_key = ?
                """,
                (profile_level, profile_key),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def list_profiles(
        self,
        *,
        profile_level: str | None = None,
        limit: int = 50,
    ) -> list[LearningProfileRecord]:
        query = """
            SELECT profile_level, profile_key, session_id, workspace, topic,
                   summary_json, facts_json, metadata_json, created_at, updated_at
            FROM learning_profiles
        """
        params: tuple[Any, ...]
        if profile_level:
            query += " WHERE profile_level = ?"
            params = (profile_level, limit)
            query += " ORDER BY updated_at DESC LIMIT ?"
        else:
            params = (limit,)
            query += " ORDER BY updated_at DESC LIMIT ?"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def create_push_record(
        self,
        *,
        session_id: str,
        profile_level: str,
        profile_key: str,
        push_type: str,
        title: str,
        message: str,
        payload: dict[str, Any],
        status: str,
        created_at: str,
    ) -> PushRecord:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO learning_push_records (
                    session_id, profile_level, profile_key, push_type, title,
                    message, payload_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    profile_level,
                    profile_key,
                    push_type,
                    title,
                    message,
                    json.dumps(payload, ensure_ascii=False),
                    status,
                    created_at,
                ),
            )
            connection.commit()
            push_id = int(cursor.lastrowid)
        return PushRecord(
            push_id=push_id,
            session_id=session_id,
            profile_level=profile_level,
            profile_key=profile_key,
            push_type=push_type,
            title=title,
            message=message,
            payload=payload,
            status=status,
            created_at=created_at,
        )

    def list_push_records(self, *, session_id: str | None = None, limit: int = 50) -> list[PushRecord]:
        query = """
            SELECT id, session_id, profile_level, profile_key, push_type, title,
                   message, payload_json, status, created_at
            FROM learning_push_records
        """
        params: tuple[Any, ...]
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id, limit)
            query += " ORDER BY id DESC LIMIT ?"
        else:
            params = (limit,)
            query += " ORDER BY id DESC LIMIT ?"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_push(row) for row in rows]

    def _row_to_profile(self, row: sqlite3.Row) -> LearningProfileRecord:
        return LearningProfileRecord(
            profile_level=str(row["profile_level"]),
            profile_key=str(row["profile_key"]),
            session_id=str(row["session_id"]),
            workspace=str(row["workspace"]),
            topic=str(row["topic"]),
            summary=json.loads(str(row["summary_json"])),
            facts=json.loads(str(row["facts_json"])),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _row_to_push(self, row: sqlite3.Row) -> PushRecord:
        return PushRecord(
            push_id=int(row["id"]),
            session_id=str(row["session_id"]),
            profile_level=str(row["profile_level"]),
            profile_key=str(row["profile_key"]),
            push_type=str(row["push_type"]),
            title=str(row["title"]),
            message=str(row["message"]),
            payload=json.loads(str(row["payload_json"])),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
        )
