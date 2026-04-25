from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.server.protocol import OrchestratorParams, OrchestratorRequest, build_event

if TYPE_CHECKING:
    from backend.server.app import main, run_server

__all__ = ["OrchestratorParams", "OrchestratorRequest", "build_event", "main", "run_server"]


def __getattr__(name: str) -> Any:
    if name in {"main", "run_server"}:
        from backend.server.app import main as _main
        from backend.server.app import run_server as _run_server

        if name == "main":
            return _main
        return _run_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


