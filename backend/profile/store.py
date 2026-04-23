from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.db.models import LearningProfileModel, LearningPushRecordModel
from backend.db.session import OrchestratorDatabase


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
        self.database = OrchestratorDatabase(path)

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
        with self.database.SessionLocal() as db:
            statement = sqlite_insert(LearningProfileModel).values(
                profile_level=profile_level,
                profile_key=profile_key,
                session_id=session_id,
                workspace=workspace,
                topic=topic,
                summary_json=summary,
                facts_json=facts,
                metadata_json=metadata,
                created_at=created_at,
                updated_at=updated_at,
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["profile_level", "profile_key"],
                    set_={
                        "session_id": session_id,
                        "workspace": workspace,
                        "topic": topic,
                        "summary_json": summary,
                        "facts_json": facts,
                        "metadata_json": metadata,
                        "updated_at": updated_at,
                    },
                )
            )
            db.commit()

    def get_profile(self, *, profile_level: str, profile_key: str) -> LearningProfileRecord | None:
        with self.database.SessionLocal() as db:
            row = db.scalars(
                select(LearningProfileModel).where(
                    LearningProfileModel.profile_level == profile_level,
                    LearningProfileModel.profile_key == profile_key,
                )
            ).first()
        return self._row_to_profile(row) if row is not None else None

    def list_profiles(
        self,
        *,
        profile_level: str | None = None,
        limit: int = 50,
    ) -> list[LearningProfileRecord]:
        with self.database.SessionLocal() as db:
            statement = select(LearningProfileModel).order_by(LearningProfileModel.updated_at.desc()).limit(limit)
            if profile_level:
                statement = statement.where(LearningProfileModel.profile_level == profile_level)
            rows = db.scalars(statement).all()
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
        with self.database.SessionLocal() as db:
            row = LearningPushRecordModel(
                session_id=session_id,
                profile_level=profile_level,
                profile_key=profile_key,
                push_type=push_type,
                title=title,
                message=message,
                payload_json=payload,
                status=status,
                created_at=created_at,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return self._row_to_push(row)

    def list_push_records(self, *, session_id: str | None = None, limit: int = 50) -> list[PushRecord]:
        with self.database.SessionLocal() as db:
            statement = select(LearningPushRecordModel).order_by(LearningPushRecordModel.id.desc()).limit(limit)
            if session_id:
                statement = statement.where(LearningPushRecordModel.session_id == session_id)
            rows = db.scalars(statement).all()
        return [self._row_to_push(row) for row in rows]

    def _row_to_profile(self, row: LearningProfileModel) -> LearningProfileRecord:
        return LearningProfileRecord(
            profile_level=row.profile_level,
            profile_key=row.profile_key,
            session_id=row.session_id,
            workspace=row.workspace,
            topic=row.topic,
            summary=dict(row.summary_json or {}),
            facts=list(row.facts_json or []),
            metadata=dict(row.metadata_json or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _row_to_push(self, row: LearningPushRecordModel) -> PushRecord:
        return PushRecord(
            push_id=int(row.id),
            session_id=row.session_id,
            profile_level=row.profile_level,
            profile_key=row.profile_key,
            push_type=row.push_type,
            title=row.title,
            message=row.message,
            payload=dict(row.payload_json or {}),
            status=row.status,
            created_at=row.created_at,
        )
