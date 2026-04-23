from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from pathlib import Path

from backend.sessions.state import OrchestratorSessionState
from backend.storage.models import SessionRow, build_artifact_rows, build_error_rows, build_message_rows


class SQLiteSessionStore:
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
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    runner TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    task TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    stop_reason TEXT NOT NULL,
                    latest_summary TEXT NOT NULL,
                    latest_artifact_summary TEXT NOT NULL,
                    permission_summary TEXT NOT NULL,
                    session_info_summary TEXT NOT NULL,
                    mcp_status_summary TEXT NOT NULL,
                    active_worker TEXT NOT NULL,
                    active_session_mode TEXT NOT NULL,
                    active_worker_profile TEXT NOT NULL,
                    active_worker_task_id TEXT NOT NULL,
                    active_worker_can_interrupt INTEGER NOT NULL,
                    awaiting_input INTEGER NOT NULL,
                    pending_user_prompt TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    error TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, snapshot_version)
                );

                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, seq)
                );

                CREATE TABLE IF NOT EXISTS session_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    error_layer TEXT NOT NULL,
                    error_code TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    retryable INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    worker TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, seq, message)
                );

                CREATE TABLE IF NOT EXISTS session_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    size INTEGER,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, path)
                );
                """
            )
            connection.commit()

    def save_session(self, session: OrchestratorSessionState) -> None:
        row = SessionRow.from_session(session)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, task_id, node_id, runner, workspace, task, goal,
                    status, phase, stop_reason, latest_summary, latest_artifact_summary,
                    permission_summary, session_info_summary, mcp_status_summary,
                    active_worker, active_session_mode, active_worker_profile,
                    active_worker_task_id, active_worker_can_interrupt, awaiting_input,
                    pending_user_prompt, snapshot_version, created_at, updated_at,
                    completed_at, error
                ) VALUES (
                    :session_id, :task_id, :node_id, :runner, :workspace, :task, :goal,
                    :status, :phase, :stop_reason, :latest_summary, :latest_artifact_summary,
                    :permission_summary, :session_info_summary, :mcp_status_summary,
                    :active_worker, :active_session_mode, :active_worker_profile,
                    :active_worker_task_id, :active_worker_can_interrupt, :awaiting_input,
                    :pending_user_prompt, :snapshot_version, :created_at, :updated_at,
                    :completed_at, :error
                )
                ON CONFLICT(session_id) DO UPDATE SET
                    task_id=excluded.task_id,
                    node_id=excluded.node_id,
                    runner=excluded.runner,
                    workspace=excluded.workspace,
                    task=excluded.task,
                    goal=excluded.goal,
                    status=excluded.status,
                    phase=excluded.phase,
                    stop_reason=excluded.stop_reason,
                    latest_summary=excluded.latest_summary,
                    latest_artifact_summary=excluded.latest_artifact_summary,
                    permission_summary=excluded.permission_summary,
                    session_info_summary=excluded.session_info_summary,
                    mcp_status_summary=excluded.mcp_status_summary,
                    active_worker=excluded.active_worker,
                    active_session_mode=excluded.active_session_mode,
                    active_worker_profile=excluded.active_worker_profile,
                    active_worker_task_id=excluded.active_worker_task_id,
                    active_worker_can_interrupt=excluded.active_worker_can_interrupt,
                    awaiting_input=excluded.awaiting_input,
                    pending_user_prompt=excluded.pending_user_prompt,
                    snapshot_version=excluded.snapshot_version,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at,
                    error=excluded.error
                """,
                row.to_record(),
            )
            self._replace_messages(connection, session)
            self._sync_errors(connection, session)
            self._replace_artifacts(connection, session)
            connection.commit()

    def save_snapshot(self, session: OrchestratorSessionState) -> None:
        snapshot = session.build_snapshot()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO session_snapshots (
                    session_id, snapshot_version, snapshot_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.snapshot_version,
                    json.dumps(snapshot, ensure_ascii=False),
                    session.updated_at,
                ),
            )
            connection.commit()

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    session_id,
                    task,
                    runner,
                    status,
                    phase,
                    latest_summary,
                    active_worker,
                    updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "sessionId": row["session_id"],
                "task": row["task"],
                "runner": row["runner"],
                "status": row["status"],
                "phase": row["phase"],
                "latestSummary": row["latest_summary"],
                "activeWorker": row["active_worker"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def get_session_snapshot(self, session_id: str) -> dict[str, object] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT snapshot_json
                FROM session_snapshots
                WHERE session_id = ?
                ORDER BY snapshot_version DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["snapshot_json"])

    def list_session_messages(self, session_id: str, *, limit: int = 200) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT seq, role, message_type, content_text, content_json, tool_name, tool_call_id, created_at
                FROM session_messages
                WHERE session_id = ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "seq": row["seq"],
                "role": row["role"],
                "messageType": row["message_type"],
                "contentText": row["content_text"],
                "contentJson": json.loads(row["content_json"] or "{}"),
                "toolName": row["tool_name"],
                "toolCallId": row["tool_call_id"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def list_session_errors(self, session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT seq, error_layer, error_code, message, details_json, retryable, phase, worker, created_at
                FROM session_errors
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "seq": row["seq"],
                "errorLayer": row["error_layer"],
                "errorCode": row["error_code"],
                "message": row["message"],
                "details": json.loads(row["details_json"] or "{}"),
                "retryable": bool(row["retryable"]),
                "phase": row["phase"],
                "worker": row["worker"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def list_session_artifacts(self, session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT path, change_type, size, summary, created_at
                FROM session_artifacts
                WHERE session_id = ?
                ORDER BY created_at DESC, path ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "path": row["path"],
                "changeType": row["change_type"],
                "size": row["size"],
                "summary": row["summary"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def _replace_messages(self, connection: sqlite3.Connection, session: OrchestratorSessionState) -> None:
        connection.execute("DELETE FROM session_messages WHERE session_id = ?", (session.session_id,))
        for row in build_message_rows(session):
            connection.execute(
                """
                INSERT INTO session_messages (
                    session_id, seq, role, message_type, content_text, content_json,
                    tool_name, tool_call_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["session_id"],
                    row["seq"],
                    row["role"],
                    row["message_type"],
                    row["content_text"],
                    json.dumps(row["content_json"], ensure_ascii=False),
                    row["tool_name"],
                    row["tool_call_id"],
                    row["created_at"],
                ),
            )

    def _sync_errors(self, connection: sqlite3.Connection, session: OrchestratorSessionState) -> None:
        for row in build_error_rows(session):
            connection.execute(
                """
                INSERT OR IGNORE INTO session_errors (
                    session_id, seq, error_layer, error_code, message, details_json,
                    retryable, phase, worker, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["session_id"],
                    row["seq"],
                    row["error_layer"],
                    row["error_code"],
                    row["message"],
                    json.dumps(row["details_json"], ensure_ascii=False),
                    1 if row["retryable"] else 0,
                    row["phase"],
                    row["worker"],
                    row["created_at"],
                ),
            )

    def _replace_artifacts(self, connection: sqlite3.Connection, session: OrchestratorSessionState) -> None:
        connection.execute("DELETE FROM session_artifacts WHERE session_id = ?", (session.session_id,))
        for row in build_artifact_rows(session):
            connection.execute(
                """
                INSERT INTO session_artifacts (
                    session_id, path, change_type, size, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["session_id"],
                    row["path"],
                    row["change_type"],
                    row["size"],
                    row["summary"],
                    row["created_at"],
                ),
            )

