from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from pathlib import Path

from sessions.state import OrchestratorSessionState
from storage.models import SessionRow


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
