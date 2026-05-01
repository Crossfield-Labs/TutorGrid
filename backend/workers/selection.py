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


@dataclass(slots=True)
class WorkerProfileSelection:
    profile: str
    reason: str


def _normalize_worker_name(name: str) -> str:
    normalized = (name or "").strip().lower()
    aliases = {"opencodeai": "opencode"}
    return aliases.get(normalized, normalized)


def select_worker(
    *,
    task: str,
    available_workers: list[str],
    preferred_worker: str | None = None,
) -> WorkerSelection:
    supported_workers = {"codex", "opencode"}
    normalized_available = [
        item
        for item in (_normalize_worker_name(value) for value in available_workers if value.strip())
        if item in supported_workers
    ]
    preferred = _normalize_worker_name(preferred_worker or "")
    task_lower = task.lower()

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
    elif any(keyword in task_lower for keyword in ("review", "analyze", "inspect", "explain", "diagnose")) and "codex" in normalized_available:
        selected = "codex"
        reason = "The task emphasizes structured analysis, which fits Codex well."
    elif any(
        keyword in task_lower
        for keyword in ("implement", "write", "create", "fix", "patch", "edit", "refactor", "generate")
    ) and "opencode" in normalized_available:
        selected = "opencode"
        reason = "The task emphasizes concrete implementation work, which fits OpenCode well."
    else:
        priority = [name for name in ("opencode", "codex") if name in normalized_available]
        if not priority:
            raise RuntimeError("No supported worker is available. Enable codex or opencode.")
        selected = priority[0]
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
        if requested in {"fork", "new", "resume"}:
            reasons = {
                "fork": "Fork was explicitly requested for this backend call.",
                "new": "A fresh backend session was explicitly requested.",
                "resume": "The task explicitly requested continuing the existing backend session.",
            }
            return SessionModeSelection(mode=requested, reason=reasons[requested])

    normalized_worker = _normalize_worker_name(worker)
    if normalized_worker != "codex":
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
    if any(keyword in task_lower for keyword in ("continue", "follow up", "same session")):
        return SessionModeSelection(
            mode="resume",
            reason="This looks like a follow-up request, so the existing Codex session should be resumed.",
        )
    return SessionModeSelection(
        mode="new",
        reason="This looks like a fresh delegated task, so a new Codex session will be created.",
    )


def select_worker_profile(
    *,
    worker: str,
    task: str,
    requested_profile: str | None = None,
) -> WorkerProfileSelection:
    normalized_worker = _normalize_worker_name(worker)
    return WorkerProfileSelection(
        profile="",
        reason=f"{normalized_worker or 'worker'} does not use worker profiles.",
    )
