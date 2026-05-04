"""Lightweight stdout trace logger for orchestrator development.

The orchestrator has rich event broadcasting but no human-readable stdout
logs.  When you run ``python -m backend.server.app --port 3210`` you want
a single window that tells you, in plain language, what the agent is
doing right now: which tool is being called, which worker is running,
where artifacts landed, when the LLM decided to write back to the doc.

Usage::

    from backend.observability.trace import trace
    trace("tool.start", tool="delegate_codex", session_key="svm_exp")

Output::

    [10:23:45.812] tool.start            tool=delegate_codex session_key=svm_exp

Set ``ORCHESTRATOR_TRACE=0`` to silence everything; set
``ORCHESTRATOR_TRACE_VERBOSE=1`` to also print noisy progress events.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

_DISABLED_ENV = "ORCHESTRATOR_TRACE"
_VERBOSE_ENV = "ORCHESTRATOR_TRACE_VERBOSE"
_TRUNCATE_LEN = 160

_VERBOSE_CATEGORIES = {
    "session.progress",
    "session.message.delta",
    "session.message.started",
    "session.message.completed",
    "session.subnode.started",
    "session.subnode.completed",
}


def _enabled() -> bool:
    return os.environ.get(_DISABLED_ENV, "1").strip() != "0"


def _verbose() -> bool:
    return os.environ.get(_VERBOSE_ENV, "0").strip() == "1"


def _truncate(value: Any, limit: int = _TRUNCATE_LEN) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def trace(category: str, **fields: Any) -> None:
    """Emit a single human-readable stdout line for a runtime event."""
    if not _enabled():
        return
    if category in _VERBOSE_CATEGORIES and not _verbose():
        return
    timestamp = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
    parts = [f"[{timestamp}]", f"{category:<20}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={_truncate(value)}")
    print(" ".join(parts), flush=True)


def banner(message: str) -> None:
    """Print a clearly visible separator banner for major lifecycle events."""
    if not _enabled():
        return
    line = "=" * 8
    print(f"\n{line} {message} {line}", flush=True)
