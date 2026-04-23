from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.db.models import (
    SessionArtifactModel,
    SessionErrorModel,
    SessionMessageModel,
    SessionModel,
    SessionSnapshotModel,
)
from backend.db.session import OrchestratorDatabase
from backend.sessions.state import OrchestratorSessionState
from backend.storage.models import SessionRow, build_artifact_rows, build_error_rows, build_message_rows


class SQLiteSessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.database = OrchestratorDatabase(path)

    def save_session(self, session: OrchestratorSessionState) -> None:
        row = SessionRow.from_session(session).to_record()
        with self.database.SessionLocal() as db:
            statement = sqlite_insert(SessionModel).values(**row)
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["session_id"],
                    set_={key: value for key, value in row.items() if key != "session_id"},
                )
            )
            self._replace_messages(db, session)
            self._sync_errors(db, session)
            self._replace_artifacts(db, session)
            db.commit()

    def save_snapshot(self, session: OrchestratorSessionState) -> None:
        snapshot = session.build_snapshot()
        with self.database.SessionLocal() as db:
            statement = sqlite_insert(SessionSnapshotModel).values(
                session_id=session.session_id,
                snapshot_version=session.snapshot_version,
                snapshot_json=snapshot,
                created_at=session.updated_at,
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["session_id", "snapshot_version"],
                    set_={
                        "snapshot_json": snapshot,
                        "created_at": session.updated_at,
                    },
                )
            )
            db.commit()

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, object]]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(SessionModel).order_by(SessionModel.updated_at.desc()).limit(limit)
            ).all()
        return [
            {
                "sessionId": row.session_id,
                "task": row.task,
                "runner": row.runner,
                "status": row.status,
                "phase": row.phase,
                "latestSummary": row.latest_summary,
                "activeWorker": row.active_worker,
                "updatedAt": row.updated_at,
            }
            for row in rows
        ]

    def get_session_snapshot(self, session_id: str) -> dict[str, object] | None:
        with self.database.SessionLocal() as db:
            row = db.scalars(
                select(SessionSnapshotModel)
                .where(SessionSnapshotModel.session_id == session_id)
                .order_by(SessionSnapshotModel.snapshot_version.desc())
                .limit(1)
            ).first()
        return dict(row.snapshot_json) if row is not None else None

    def list_session_messages(self, session_id: str, *, limit: int = 200) -> list[dict[str, object]]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(SessionMessageModel)
                .where(SessionMessageModel.session_id == session_id)
                .order_by(SessionMessageModel.seq.asc())
                .limit(limit)
            ).all()
        return [
            {
                "seq": row.seq,
                "role": row.role,
                "messageType": row.message_type,
                "contentText": row.content_text,
                "contentJson": dict(row.content_json or {}),
                "toolName": row.tool_name,
                "toolCallId": row.tool_call_id,
                "createdAt": row.created_at,
            }
            for row in rows
        ]

    def list_session_errors(self, session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(SessionErrorModel)
                .where(SessionErrorModel.session_id == session_id)
                .order_by(SessionErrorModel.id.desc())
                .limit(limit)
            ).all()
        return [
            {
                "seq": row.seq,
                "errorLayer": row.error_layer,
                "errorCode": row.error_code,
                "message": row.message,
                "details": dict(row.details_json or {}),
                "retryable": bool(row.retryable),
                "phase": row.phase,
                "worker": row.worker,
                "createdAt": row.created_at,
            }
            for row in rows
        ]

    def list_session_artifacts(self, session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with self.database.SessionLocal() as db:
            rows = db.scalars(
                select(SessionArtifactModel)
                .where(SessionArtifactModel.session_id == session_id)
                .order_by(SessionArtifactModel.created_at.desc(), SessionArtifactModel.path.asc())
                .limit(limit)
            ).all()
        return [
            {
                "path": row.path,
                "changeType": row.change_type,
                "size": row.size,
                "summary": row.summary,
                "createdAt": row.created_at,
            }
            for row in rows
        ]

    def _replace_messages(self, db, session: OrchestratorSessionState) -> None:
        db.execute(delete(SessionMessageModel).where(SessionMessageModel.session_id == session.session_id))
        rows = build_message_rows(session)
        if not rows:
            return
        db.add_all(
            [
                SessionMessageModel(
                    session_id=row["session_id"],
                    seq=row["seq"],
                    role=row["role"],
                    message_type=row["message_type"],
                    content_text=row["content_text"],
                    content_json=row["content_json"],
                    tool_name=row["tool_name"],
                    tool_call_id=row["tool_call_id"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        )

    def _sync_errors(self, db, session: OrchestratorSessionState) -> None:
        for row in build_error_rows(session):
            statement = sqlite_insert(SessionErrorModel).values(
                session_id=row["session_id"],
                seq=row["seq"],
                error_layer=row["error_layer"],
                error_code=row["error_code"],
                message=row["message"],
                details_json=row["details_json"],
                retryable=bool(row["retryable"]),
                phase=row["phase"],
                worker=row["worker"],
                created_at=row["created_at"],
            )
            db.execute(
                statement.on_conflict_do_nothing(
                    index_elements=["session_id", "seq", "message"],
                )
            )

    def _replace_artifacts(self, db, session: OrchestratorSessionState) -> None:
        db.execute(delete(SessionArtifactModel).where(SessionArtifactModel.session_id == session.session_id))
        rows = build_artifact_rows(session)
        if not rows:
            return
        db.add_all(
            [
                SessionArtifactModel(
                    session_id=row["session_id"],
                    path=row["path"],
                    change_type=row["change_type"],
                    size=row["size"],
                    summary=row["summary"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        )
