from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WorkerSelection:
    worker: str
    reason: str
    fallback_order: list[str]


@dataclass(slots=True)
class SessionModeSelection:
    mode: str
    reason: str


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


def select_session_mode(
    *,
    worker: str,
    task: str,
    requested_mode: str | None = None,
    has_existing_session: bool = False,
) -> SessionModeSelection:
    requested = (requested_mode or "").strip().lower()
    if requested:
        if requested not in {"auto", "new", "resume", "fork"}:
            raise RuntimeError(f"Unsupported session mode: {requested_mode}")
        if requested == "resume" and not has_existing_session:
            return SessionModeSelection(
                mode="new",
                reason="Resume was requested but no existing session was available, so a new session will be created.",
            )
        if requested == "fork":
            return SessionModeSelection(
                mode="fork",
                reason="Fork was explicitly requested for this backend call.",
            )
        if requested == "new":
            return SessionModeSelection(
                mode="new",
                reason="A fresh backend session was explicitly requested.",
            )
        if requested == "resume":
            return SessionModeSelection(
                mode="resume",
                reason="The task explicitly requested continuing the existing backend session.",
            )

    if worker != "codex":
        return SessionModeSelection(
            mode="new",
            reason="Only Codex currently supports native long-lived sessions in this orchestration layer.",
        )

    if not has_existing_session:
        return SessionModeSelection(
            mode="new",
            reason="No previous Codex session is available yet, so a new session will be created.",
        )

    task_lower = task.lower()
    resume_keywords = (
        "continue",
        "follow up",
        "based on the previous",
        "same session",
        "继续",
        "接着",
        "在刚才基础上",
        "在上次基础上",
        "沿着刚才",
        "继续修改",
        "继续完善",
        "继续修",
    )
    if any(keyword in task_lower for keyword in resume_keywords):
        return SessionModeSelection(
            mode="resume",
            reason="This looks like a follow-up request, so the existing Codex session should be resumed.",
        )

    return SessionModeSelection(
        mode="new",
        reason="This looks like a fresh delegated task, so a new Codex session will be created.",
    )
