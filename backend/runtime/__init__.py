from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.runtime.graph import build_runtime_graph
    from backend.runtime.runtime import OrchestratorRuntime
    from backend.runtime.state import RuntimeState, create_initial_state

__all__ = ["OrchestratorRuntime", "RuntimeState", "build_runtime_graph", "create_initial_state"]


def __getattr__(name: str) -> Any:
    if name == "build_runtime_graph":
        from backend.runtime.graph import build_runtime_graph as _build_runtime_graph

        return _build_runtime_graph
    if name == "OrchestratorRuntime":
        from backend.runtime.runtime import OrchestratorRuntime as _OrchestratorRuntime

        return _OrchestratorRuntime
    if name == "RuntimeState":
        from backend.runtime.state import RuntimeState as _RuntimeState

        return _RuntimeState
    if name == "create_initial_state":
        from backend.runtime.state import create_initial_state as _create_initial_state

        return _create_initial_state
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


