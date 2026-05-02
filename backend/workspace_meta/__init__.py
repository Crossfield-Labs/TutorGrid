"""Workspace 元数据模块。

负责管理产品级"工作区"概念：
- 工作区元数据（name / 视觉外观 / 绑定的文件系统目录）
- 工作区下的 Hyperdoc 元数据列表

文件系统层（实际文件读写）继续走 Electron 的 workspace IPC，
此模块仅维护元数据持久化。
"""

from backend.workspace_meta.store import WorkspaceMetaStore  # noqa: F401
from backend.workspace_meta.service import WorkspaceMetaService  # noqa: F401
