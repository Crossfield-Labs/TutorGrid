"""Workspace 元数据业务封装。"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from backend.workspace_meta.store import (
    HyperdocMetaRow,
    WorkspaceMetaStore,
    WorkspaceRow,
)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class WorkspaceMetaService:
    def __init__(self, db_path: Path) -> None:
        self.store = WorkspaceMetaStore(db_path)

    # ---------------- workspaces ----------------

    def list_workspaces(self) -> list[dict[str, Any]]:
        return [row.to_dict() for row in self.store.list_workspaces()]

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        row = self.store.get_workspace(workspace_id)
        return row.to_dict() if row else None

    def create_workspace(
        self,
        *,
        name: str,
        fs_root: str,
        appearance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("name 不能为空")
        if not fs_root.strip():
            raise ValueError("fs_root 不能为空")
        now = _now_ms()
        row = WorkspaceRow(
            id=_new_id("ws"),
            name=name.strip(),
            fs_root=fs_root.strip(),
            appearance=appearance or {},
            created_at=now,
            updated_at=now,
        )
        self.store.create_workspace(row)
        return row.to_dict()

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        fs_root: str | None = None,
        appearance: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        updated = self.store.update_workspace(
            workspace_id,
            name=name.strip() if name is not None else None,
            fs_root=fs_root.strip() if fs_root is not None else None,
            appearance=appearance,
            updated_at=_now_ms(),
        )
        return updated.to_dict() if updated else None

    def delete_workspace(self, workspace_id: str) -> bool:
        return self.store.delete_workspace(workspace_id)

    # ---------------- hyperdocs ----------------

    def list_hyperdocs(self, workspace_id: str) -> list[dict[str, Any]]:
        if self.store.get_workspace(workspace_id) is None:
            raise ValueError(f"工作区不存在: {workspace_id}")
        return [row.to_dict() for row in self.store.list_hyperdocs(workspace_id)]

    def create_hyperdoc(
        self,
        *,
        workspace_id: str,
        title: str,
        file_rel_path: str,
    ) -> dict[str, Any]:
        if self.store.get_workspace(workspace_id) is None:
            raise ValueError(f"工作区不存在: {workspace_id}")
        if not title.strip():
            raise ValueError("title 不能为空")
        if not file_rel_path.strip():
            raise ValueError("file_rel_path 不能为空")
        now = _now_ms()
        row = HyperdocMetaRow(
            id=_new_id("doc"),
            workspace_id=workspace_id,
            title=title.strip(),
            file_rel_path=file_rel_path.strip(),
            created_at=now,
            last_edited_at=now,
        )
        self.store.create_hyperdoc(row)
        return row.to_dict()

    def delete_hyperdoc(self, hyperdoc_id: str) -> bool:
        return self.store.delete_hyperdoc(hyperdoc_id)
