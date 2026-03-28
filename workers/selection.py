from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WorkerSelection:
    worker: str
    reason: str
    fallback_order: list[str]


def select_worker(
    *,
    task: str,
    available_workers: list[str],
    preferred_worker: str | None = None,
) -> WorkerSelection:
    normalized_available = [item.strip().lower() for item in available_workers if item.strip()]
    task_lower = task.lower()
    preferred = (preferred_worker or "").strip().lower()

    if preferred:
        if preferred not in normalized_available:
            raise RuntimeError(f"Requested worker is not available: {preferred_worker}")
        return WorkerSelection(
            worker=preferred,
            reason=f"The task explicitly requested the {preferred} backend.",
            fallback_order=[item for item in normalized_available if item != preferred],
        )

    if "codex" in task_lower and "codex" in normalized_available:
        selected = "codex"
        reason = "The task explicitly mentions Codex."
    elif "opencode" in task_lower and "opencode" in normalized_available:
        selected = "opencode"
        reason = "The task explicitly mentions OpenCode."
    elif any(keyword in task_lower for keyword in ("review", "analyze", "inspect", "explain", "summary", "report")) and "codex" in normalized_available:
        selected = "codex"
        reason = "The task emphasizes code review or structured analysis, which fits Codex well."
    elif any(keyword in task_lower for keyword in ("implement", "write", "create", "fix", "patch", "edit", "modify", "scaffold", "refactor", "repair")) and "opencode" in normalized_available:
        selected = "opencode"
        reason = "The task emphasizes concrete code generation or editing, which fits OpenCode well."
    else:
        selected = "opencode" if "opencode" in normalized_available else normalized_available[0]
        reason = "Defaulting to the most execution-oriented backend available."

    return WorkerSelection(
        worker=selected,
        reason=reason,
        fallback_order=[item for item in normalized_available if item != selected],
    )
