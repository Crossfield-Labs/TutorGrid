from __future__ import annotations

import time
import uuid
from typing import Any

from backend.runtime.context_registry import get_runtime_context
from backend.sessions.state import OrchestratorSessionState

_VALID_PLACEMENTS = {"append", "replace_section", "inline_after"}
_VALID_KINDS = {"report", "explanation", "summary", "code_output", "citation"}


async def write_to_doc(
    session: OrchestratorSessionState | None,
    *,
    content: str,
    doc_id: str = "",
    kind: str = "report",
    title: str = "",
    placement: str = "append",
    anchor: str = "",
    citations: list[dict[str, Any]] | None = None,
) -> str:
    if not content or not content.strip():
        return "Error: write_to_doc requires non-empty content."
    if session is None:
        return "Error: orchestrator session is unavailable; cannot write back to the document."
    target_doc_id = (doc_id or "").strip() or _resolve_session_doc_id(session)
    if not target_doc_id:
        return "Error: no doc_id available for this task; cannot write back to the document."
    normalized_kind = (kind or "report").strip().lower() or "report"
    if normalized_kind not in _VALID_KINDS:
        normalized_kind = "report"
    normalized_placement = (placement or "append").strip().lower() or "append"
    if normalized_placement not in _VALID_PLACEMENTS:
        normalized_placement = "append"
    write_id = f"docwrite_{uuid.uuid4().hex[:10]}"
    payload: dict[str, Any] = {
        "write_id": write_id,
        "task_id": session.task_id,
        "session_id": session.session_id,
        "doc_id": target_doc_id,
        "kind": normalized_kind,
        "title": (title or "").strip(),
        "content": content,
        "placement": normalized_placement,
        "anchor": (anchor or "").strip(),
        "citations": list(citations or []),
        "created_at": int(time.time() * 1000),
    }
    history = session.context.setdefault("doc_writes", [])
    if isinstance(history, list):
        history.append(payload)
    runtime_context = get_runtime_context(session.session_id)
    callback = runtime_context.get("emit_doc_write") if runtime_context else None
    if callback is not None:
        try:
            await callback(payload)
        except Exception as error:  # pragma: no cover - defensive
            return f"Wrote {write_id} to local trace, but broadcast failed: {error}"
    return f"Wrote {write_id} to document {target_doc_id} (placement={normalized_placement}, kind={normalized_kind})."


def _resolve_session_doc_id(session: OrchestratorSessionState) -> str:
    context = session.context if isinstance(session.context, dict) else {}
    for key in ("doc_id", "docId", "hyperdoc_id", "hyperdocId"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
