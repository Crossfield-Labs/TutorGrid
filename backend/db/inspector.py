from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.db.models import (
    LearningProfileModel,
    LearningPushRecordModel,
    MemoryDocumentModel,
    SessionArtifactModel,
    SessionErrorModel,
    SessionMessageModel,
    SessionModel,
)
from backend.db.session import OrchestratorDatabase


class DatabaseInspector:
    def __init__(self, path: Path | None = None) -> None:
        db_path = path or Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
        self.database = OrchestratorDatabase(db_path)

    def query(
        self,
        *,
        table: str,
        session_id: str = "",
        profile_level: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_table = table.strip().lower()
        with self.database.SessionLocal() as db:
            if normalized_table == "sessions":
                rows = db.scalars(select(SessionModel).order_by(SessionModel.updated_at.desc()).limit(limit)).all()
                return [
                    {
                        "sessionId": row.session_id,
                        "task": row.task,
                        "status": row.status,
                        "phase": row.phase,
                        "updatedAt": row.updated_at,
                    }
                    for row in rows
                ]
            if normalized_table == "session_messages":
                statement = select(SessionMessageModel).order_by(SessionMessageModel.seq.asc()).limit(limit)
                if session_id:
                    statement = statement.where(SessionMessageModel.session_id == session_id)
                rows = db.scalars(statement).all()
                return [
                    {
                        "sessionId": row.session_id,
                        "seq": row.seq,
                        "role": row.role,
                        "messageType": row.message_type,
                        "contentText": row.content_text,
                    }
                    for row in rows
                ]
            if normalized_table == "session_errors":
                statement = select(SessionErrorModel).order_by(SessionErrorModel.id.desc()).limit(limit)
                if session_id:
                    statement = statement.where(SessionErrorModel.session_id == session_id)
                rows = db.scalars(statement).all()
                return [
                    {
                        "sessionId": row.session_id,
                        "message": row.message,
                        "errorLayer": row.error_layer,
                        "errorCode": row.error_code,
                        "phase": row.phase,
                    }
                    for row in rows
                ]
            if normalized_table == "session_artifacts":
                statement = select(SessionArtifactModel).order_by(SessionArtifactModel.created_at.desc()).limit(limit)
                if session_id:
                    statement = statement.where(SessionArtifactModel.session_id == session_id)
                rows = db.scalars(statement).all()
                return [
                    {
                        "sessionId": row.session_id,
                        "path": row.path,
                        "changeType": row.change_type,
                        "summary": row.summary,
                    }
                    for row in rows
                ]
            if normalized_table == "memory_documents":
                statement = select(MemoryDocumentModel).order_by(MemoryDocumentModel.updated_at.desc()).limit(limit)
                if session_id:
                    statement = statement.where(MemoryDocumentModel.session_id == session_id)
                rows = db.scalars(statement).all()
                return [
                    {
                        "documentId": row.document_id,
                        "sessionId": row.session_id,
                        "documentType": row.document_type,
                        "title": row.title,
                    }
                    for row in rows
                ]
            if normalized_table == "learning_profiles":
                statement = select(LearningProfileModel).order_by(LearningProfileModel.updated_at.desc()).limit(limit)
                if profile_level:
                    statement = statement.where(LearningProfileModel.profile_level == profile_level)
                rows = db.scalars(statement).all()
                return [
                    {
                        "profileLevel": row.profile_level,
                        "profileKey": row.profile_key,
                        "workspace": row.workspace,
                        "topic": row.topic,
                        "summary": row.summary_json,
                    }
                    for row in rows
                ]
            if normalized_table == "learning_push_records":
                rows = db.scalars(
                    select(LearningPushRecordModel).order_by(LearningPushRecordModel.id.desc()).limit(limit)
                ).all()
                return [
                    {
                        "pushId": row.id,
                        "sessionId": row.session_id,
                        "title": row.title,
                        "status": row.status,
                    }
                    for row in rows
                ]
        raise ValueError(f"Unsupported table: {table}")

    def query_json(
        self,
        *,
        table: str,
        session_id: str = "",
        profile_level: str = "",
        limit: int = 20,
    ) -> str:
        return json.dumps(
            self.query(
                table=table,
                session_id=session_id,
                profile_level=profile_level,
                limit=limit,
            ),
            ensure_ascii=False,
            indent=2,
        )
