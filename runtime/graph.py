from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.nodes.await_user import await_user_node
from runtime.nodes.finalize import finalize_node
from runtime.nodes.planning import planning_node
from runtime.nodes.tools import tools_node
from runtime.nodes.verify import verify_node
from runtime.routes.next_step import route_after_planning
from runtime.routes.post_tools import route_after_tools
from runtime.state import RuntimeState

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover
    END = "__end__"
    StateGraph = None


@dataclass(slots=True)
class GraphBuildResult:
    graph: Any
    available: bool


def build_runtime_graph() -> GraphBuildResult:
    if StateGraph is None:
        return GraphBuildResult(graph=None, available=False)

    graph = StateGraph(RuntimeState)
    graph.add_node("planning", planning_node)
    graph.add_node("tools", tools_node)
    graph.add_node("await_user", await_user_node)
    graph.add_node("verify", verify_node)
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("planning")
    graph.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "tools": "tools",
            "await_user": "await_user",
            "verify": "verify",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "verify": "verify",
            "finalize": "finalize",
        },
    )
    graph.add_edge("await_user", "planning")
    graph.add_edge("verify", "planning")
    graph.add_edge("finalize", END)
    return GraphBuildResult(graph=graph.compile(), available=True)

