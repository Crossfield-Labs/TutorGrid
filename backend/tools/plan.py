"""declare_plan tool — let the LLM declare its high-level plan up front.

The orchestration UI renders one tile per declared step BEFORE execution
starts. Steps move pending → running → done as raw nodes (delegate_*,
write_to_doc, await_user) match into them at runtime. This is the
plan-and-execute contract: the user sees the *intended chain* first, then
watches it fill in.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from backend.runtime.context_registry import get_runtime_context
from backend.sessions.state import OrchestratorSessionState

_VALID_KINDS = {"worker", "doc_write", "await_user", "inspect"}


async def declare_plan(
    session: OrchestratorSessionState | None,
    *,
    steps: list[dict[str, Any]] | str,
    replace: bool = False,
) -> str:
    if session is None:
        return "Error: orchestrator session is unavailable; cannot declare plan."

    parsed_steps = _parse_steps(steps)
    if not parsed_steps:
        return "Error: declare_plan requires at least one step with a non-empty label."
    if len(parsed_steps) > 8:
        return "Error: at most 8 steps allowed in a plan; if you need more, finish in phases."

    plan_id = f"plan_{uuid.uuid4().hex[:10]}"
    declared_at = int(time.time() * 1000)

    existing = session.context.get("plan") if isinstance(session.context, dict) else None
    if not replace and isinstance(existing, dict) and existing.get("steps"):
        # Merge: preserve states of already-completed steps, append new ones,
        # patch labels for matching ids/labels.
        merged = _merge_plan(existing, parsed_steps, plan_id, declared_at)
    else:
        merged = {
            "plan_id": plan_id,
            "declared_at": declared_at,
            "steps": [
                _normalize_step(step, idx, declared_at)
                for idx, step in enumerate(parsed_steps)
            ],
        }

    session.context["plan"] = merged

    runtime_context = get_runtime_context(session.session_id)
    callback = runtime_context.get("emit_plan") if runtime_context else None
    if callback is not None:
        try:
            await callback(
                {
                    "task_id": session.task_id,
                    "session_id": session.session_id,
                    "doc_id": str(session.context.get("doc_id") or ""),
                    "plan_id": merged["plan_id"],
                    "declared_at": merged["declared_at"],
                    "steps": list(merged["steps"]),
                    "replace": bool(replace),
                }
            )
        except Exception as error:  # pragma: no cover - defensive
            return (
                f"Plan stored locally (plan_id={merged['plan_id']}) but broadcast failed: {error}"
            )

    return (
        f"Plan declared: {len(merged['steps'])} step(s) [{merged['plan_id']}]. "
        "You can now execute via delegate_* / write_to_doc / await_user."
    )


# All the field-name variants LLMs might use for the same concept.
# We coerce them all into our canonical names before processing.
_LABEL_KEYS = ("label", "name", "title", "step_name", "stepName", "step", "summary")
_BRIEF_KEYS = ("brief", "description", "desc", "detail", "details", "subtitle", "explanation")
_KIND_KEYS = ("kind", "type", "category", "step_type", "stepType")
_WORKER_KEYS = ("expected_worker", "expectedWorker", "worker", "backend", "agent")
_SESSION_KEYS = ("expected_session_key", "expectedSessionKey", "session_key", "sessionKey", "session")
_ID_KEYS = ("id", "step_id", "stepId", "key")


def _pick(raw: dict[str, Any], keys: tuple[str, ...]) -> str:
    for k in keys:
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v not in (None, "", []):
            return str(v).strip()
    return ""


def _parse_steps(steps: Any) -> list[dict[str, Any]]:
    if isinstance(steps, str):
        # Some providers stringify list args; tolerate JSON-ish input.
        try:
            import json as _json

            decoded = _json.loads(steps)
            steps = decoded
        except Exception:
            return []
    # Some LLMs wrap the steps in {"steps": [...]} accidentally
    if isinstance(steps, dict):
        for key in ("steps", "plan", "items", "list"):
            if isinstance(steps.get(key), list):
                steps = steps[key]
                break
        else:
            # single step passed as dict
            steps = [steps]
    if not isinstance(steps, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for raw in steps:
        if not isinstance(raw, dict):
            # If it's a plain string, treat as a label-only step
            if isinstance(raw, str) and raw.strip():
                cleaned.append({"label": raw.strip()})
            continue
        if not _pick(raw, _LABEL_KEYS):
            continue
        cleaned.append(raw)
    return cleaned


def _normalize_step(step: dict[str, Any], idx: int, declared_at: int) -> dict[str, Any]:
    kind = _pick(step, _KIND_KEYS).lower() or "worker"
    if kind not in _VALID_KINDS:
        kind = "worker"
    step_id = _pick(step, _ID_KEYS) or f"step_{idx + 1}"
    return {
        "id": step_id,
        "index": idx + 1,
        "label": _pick(step, _LABEL_KEYS),
        "kind": kind,
        "brief": _pick(step, _BRIEF_KEYS),
        "expected_worker": _pick(step, _WORKER_KEYS),
        "expected_session_key": _pick(step, _SESSION_KEYS),
        "status": "pending",
        "node_ids": [],
        "started_at": 0,
        "ended_at": 0,
        "duration_ms": 0,
        "declared_at": declared_at,
    }


def _merge_plan(
    existing: dict[str, Any],
    incoming_steps: list[dict[str, Any]],
    new_plan_id: str,
    declared_at: int,
) -> dict[str, Any]:
    existing_steps = list(existing.get("steps") or [])
    by_id = {str(s.get("id")): s for s in existing_steps if isinstance(s, dict)}
    by_label = {str(s.get("label")): s for s in existing_steps if isinstance(s, dict)}

    merged_steps: list[dict[str, Any]] = []
    for idx, step in enumerate(incoming_steps):
        normalized = _normalize_step(step, idx, declared_at)
        prior = by_id.get(normalized["id"]) or by_label.get(normalized["label"])
        if prior and prior.get("status") in {"running", "done", "failed"}:
            # keep prior live state, refresh label/brief in case LLM rewrote them
            normalized = {**normalized, **{
                "status": prior["status"],
                "node_ids": list(prior.get("node_ids") or []),
                "started_at": prior.get("started_at") or normalized["started_at"],
                "ended_at": prior.get("ended_at") or normalized["ended_at"],
                "duration_ms": prior.get("duration_ms") or normalized["duration_ms"],
            }}
        normalized["index"] = idx + 1
        merged_steps.append(normalized)

    return {
        "plan_id": new_plan_id,
        "declared_at": declared_at,
        "previous_plan_id": existing.get("plan_id"),
        "steps": merged_steps,
    }
