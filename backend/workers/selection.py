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
    aliases = {
        "claude_sdk": "claude",
        "claude-code": "claude",
        "opencodeai": "opencode",
    }
    return aliases.get(normalized, normalized)


def select_worker(
    *,
    task: str,
    available_workers: list[str],
    preferred_worker: str | None = None,
) -> WorkerSelection:
    normalized_available = [_normalize_worker_name(item) for item in available_workers if item.strip()]
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

    if "claude" in task_lower and "claude" in normalized_available:
        selected = "claude"
        reason = "The task explicitly mentions Claude."
    elif "codex" in task_lower and "codex" in normalized_available:
        selected = "codex"
        reason = "The task explicitly mentions Codex."
    elif "opencode" in task_lower and "opencode" in normalized_available:
        selected = "opencode"
        reason = "The task explicitly mentions OpenCode."
    elif any(
        keyword in task_lower
        for keyword in (
            "document",
            "docs",
            "documentation",
            "report",
            "research",
            "outline",
            "writeup",
            "summary",
            "readme",
            "architecture",
            "usage",
            "guide",
            "学习",
            "讲解",
            "文档",
            "报告",
            "总结",
        )
    ) and "claude" in normalized_available:
        selected = "claude"
        reason = "The task looks documentation- or research-heavy, which fits Claude well."
    elif any(keyword in task_lower for keyword in ("review", "analyze", "inspect", "explain")) and "codex" in normalized_available:
        selected = "codex"
        reason = "The task emphasizes structured analysis, which fits Codex well."
    elif any(keyword in task_lower for keyword in ("implement", "write", "create", "fix", "patch", "edit", "refactor")) and "opencode" in normalized_available:
        selected = "opencode"
        reason = "The task emphasizes concrete implementation work, which fits OpenCode well."
    else:
        priority = [name for name in ("opencode", "codex", "claude") if name in normalized_available]
        selected = priority[0] if priority else normalized_available[0]
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
    if normalized_worker not in {"codex", "claude"}:
        return SessionModeSelection(
            mode="new",
            reason="Only Codex and Claude currently support native long-lived sessions in this orchestration layer.",
        )
    if not has_existing_session:
        return SessionModeSelection(
            mode="new",
            reason=f"No previous {normalized_worker.capitalize()} session is available yet, so a new session will be created.",
        )
    task_lower = task.lower()
    if any(
        keyword in task_lower
        for keyword in ("continue", "follow up", "same session", "继续", "接着", "在刚才基础上", "继续修改", "继续完善")
    ):
        return SessionModeSelection(
            mode="resume",
            reason=f"This looks like a follow-up request, so the existing {normalized_worker.capitalize()} session should be resumed.",
        )
    return SessionModeSelection(
        mode="new",
        reason=f"This looks like a fresh delegated task, so a new {normalized_worker.capitalize()} session will be created.",
    )


def select_worker_profile(
    *,
    worker: str,
    task: str,
    requested_profile: str | None = None,
) -> WorkerProfileSelection:
    normalized_worker = _normalize_worker_name(worker)
    requested = (requested_profile or "").strip().lower()
    if normalized_worker != "claude":
        return WorkerProfileSelection(profile="", reason=f"{normalized_worker or 'worker'} does not use Claude task profiles.")
    valid_profiles = {"code", "doc", "study", "research"}
    if requested:
        if requested not in valid_profiles:
            raise RuntimeError(f"Unsupported Claude profile: {requested_profile}")
        return WorkerProfileSelection(profile=requested, reason=f"The task explicitly requested the Claude {requested} profile.")
    task_lower = task.lower()
    if any(keyword in task_lower for keyword in ("study", "learning", "teach", "学习", "讲解", "教程", "课程")):
        return WorkerProfileSelection(profile="study", reason="The task looks like a learning or teaching flow, so the Claude study profile fits best.")
    if any(keyword in task_lower for keyword in ("document", "docs", "documentation", "readme", "文档", "说明", ".md")):
        return WorkerProfileSelection(profile="doc", reason="The task emphasizes documentation artifacts, so the Claude doc profile fits best.")
    if any(keyword in task_lower for keyword in ("research", "investigate", "compare", "summary", "总结", "调研", "比较")):
        return WorkerProfileSelection(profile="research", reason="The task emphasizes synthesis or investigation, so the Claude research profile fits best.")
    return WorkerProfileSelection(profile="code", reason="Defaulting to the Claude code profile.")

