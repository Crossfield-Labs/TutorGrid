"""SQLite 持久化层 - 工作区元数据 + Hyperdoc 元数据。

复用项目现有 SQLite DB（scratch/storage/orchestrator.sqlite3），
跟 memory / knowledge / sessions 共享同一个数据库文件。

表：
- workspaces      产品级工作区
- hyperdocs_meta  Hyperdoc 元数据（实际文档内容仍在文件系统）
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class WorkspaceRow:
    id: str
    name: str
    fs_root: str
    appearance: dict[str, Any]
    created_at: int
    updated_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "fsRoot": self.fs_root,
            "appearance": self.appearance,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass
class HyperdocMetaRow:
    id: str
    workspace_id: str
    title: str
    file_rel_path: str
    created_at: int
    last_edited_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspaceId": self.workspace_id,
            "title": self.title,
            "fileRelPath": self.file_rel_path,
            "createdAt": self.created_at,
            "lastEditedAt": self.last_edited_at,
        }


class WorkspaceMetaStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id            TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    fs_root       TEXT NOT NULL,
                    appearance    TEXT NOT NULL DEFAULT '{}',
                    created_at    INTEGER NOT NULL,
                    updated_at    INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hyperdocs_meta (
                    id              TEXT PRIMARY KEY,
                    workspace_id    TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    title           TEXT NOT NULL,
                    file_rel_path   TEXT NOT NULL,
                    created_at      INTEGER NOT NULL,
                    last_edited_at  INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_hyperdocs_meta_workspace
                ON hyperdocs_meta(workspace_id, last_edited_at DESC);
                """
            )
            connection.commit()

    # ---------------- workspaces ----------------

    def list_workspaces(self) -> list[WorkspaceRow]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, name, fs_root, appearance, created_at, updated_at "
                "FROM workspaces ORDER BY created_at ASC"
            ).fetchall()
            return [self._row_to_workspace(row) for row in rows]

    def get_workspace(self, workspace_id: str) -> WorkspaceRow | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id, name, fs_root, appearance, created_at, updated_at "
                "FROM workspaces WHERE id = ?",
                (workspace_id,),
            ).fetchone()
            return self._row_to_workspace(row) if row else None

    def create_workspace(self, row: WorkspaceRow) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO workspaces (id, name, fs_root, appearance, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row.id,
                    row.name,
                    row.fs_root,
                    json.dumps(row.appearance, ensure_ascii=False),
                    row.created_at,
                    row.updated_at,
                ),
            )
            connection.commit()

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        fs_root: str | None = None,
        appearance: dict[str, Any] | None = None,
        updated_at: int,
    ) -> WorkspaceRow | None:
        existing = self.get_workspace(workspace_id)
        if existing is None:
            return None
        new_name = name if name is not None else existing.name
        new_fs_root = fs_root if fs_root is not None else existing.fs_root
        new_appearance = appearance if appearance is not None else existing.appearance
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE workspaces SET name = ?, fs_root = ?, appearance = ?, updated_at = ? "
                "WHERE id = ?",
                (
                    new_name,
                    new_fs_root,
                    json.dumps(new_appearance, ensure_ascii=False),
                    updated_at,
                    workspace_id,
                ),
            )
            connection.commit()
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM workspaces WHERE id = ?", (workspace_id,)
            )
            connection.commit()
            return cursor.rowcount > 0

    # ---------------- hyperdocs_meta ----------------

    def list_hyperdocs(self, workspace_id: str) -> list[HyperdocMetaRow]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, workspace_id, title, file_rel_path, created_at, last_edited_at "
                "FROM hyperdocs_meta WHERE workspace_id = ? "
                "ORDER BY last_edited_at DESC",
                (workspace_id,),
            ).fetchall()
            return [self._row_to_hyperdoc(row) for row in rows]

    def get_hyperdoc(self, hyperdoc_id: str) -> HyperdocMetaRow | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id, workspace_id, title, file_rel_path, created_at, last_edited_at "
                "FROM hyperdocs_meta WHERE id = ?",
                (hyperdoc_id,),
            ).fetchone()
            return self._row_to_hyperdoc(row) if row else None

    def create_hyperdoc(self, row: HyperdocMetaRow) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO hyperdocs_meta (id, workspace_id, title, file_rel_path, created_at, last_edited_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row.id,
                    row.workspace_id,
                    row.title,
                    row.file_rel_path,
                    row.created_at,
                    row.last_edited_at,
                ),
            )
            connection.commit()

    def delete_hyperdoc(self, hyperdoc_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM hyperdocs_meta WHERE id = ?", (hyperdoc_id,)
            )
            connection.commit()
            return cursor.rowcount > 0

    # ---------------- helpers ----------------

    @staticmethod
    def _row_to_workspace(row: sqlite3.Row) -> WorkspaceRow:
        appearance_raw = row["appearance"] or "{}"
        try:
            appearance = json.loads(appearance_raw)
        except json.JSONDecodeError:
            appearance = {}
        return WorkspaceRow(
            id=row["id"],
            name=row["name"],
            fs_root=row["fs_root"],
            appearance=appearance,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_hyperdoc(row: sqlite3.Row) -> HyperdocMetaRow:
        return HyperdocMetaRow(
            id=row["id"],
            workspace_id=row["workspace_id"],
            title=row["title"],
            file_rel_path=row["file_rel_path"],
            created_at=row["created_at"],
            last_edited_at=row["last_edited_at"],
        )
