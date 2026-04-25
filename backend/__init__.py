from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.runtime.runtime import OrchestratorRuntime
    from backend.runtime.state import RuntimeState

__all__ = ["OrchestratorRuntime", "RuntimeState"]


def __getattr__(name: str) -> Any:
    """Lazily import runtime symbols for lightweight module imports/tests."""
    if name == "OrchestratorRuntime":
        from backend.runtime.runtime import OrchestratorRuntime as _OrchestratorRuntime

        return _OrchestratorRuntime
    if name == "RuntimeState":
        from backend.runtime.state import RuntimeState as _RuntimeState

        return _RuntimeState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


