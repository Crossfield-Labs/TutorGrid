from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4


class LangSmithTracer:
    def __init__(self) -> None:
        self.enabled = self._is_enabled()
        self.project_name = os.environ.get("ORCHESTRATOR_LANGSMITH_PROJECT", "").strip() or os.environ.get(
            "LANGSMITH_PROJECT", ""
        ).strip() or "pc-orchestrator-core"
        self.client = None
        if not self.enabled:
            return
        try:
            from langsmith import Client

            self.client = Client()
        except Exception:
            self.client = None
            self.enabled = False

    def start_run(
        self,
        *,
        name: str,
        run_type: str,
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        parent_run_id: str | None = None,
    ) -> str | None:
        if not self.enabled or self.client is None:
            return None
        run_id = uuid4().hex
        extra = {"metadata": metadata or {}}
        kwargs: dict[str, Any] = {"id": run_id, "extra": extra}
        if tags:
            kwargs["tags"] = tags
        if parent_run_id:
            kwargs["parent_run_id"] = parent_run_id
        try:
            self.client.create_run(
                name=name,
                inputs=inputs or {},
                run_type=run_type,
                project_name=self.project_name,
                **kwargs,
            )
            return run_id
        except Exception:
            return None

    def end_run(
        self,
        run_id: str | None,
        *,
        outputs: dict[str, Any] | None = None,
        error: str = "",
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        if not run_id or not self.enabled or self.client is None:
            return
        extra = {"metadata": metadata or {}}
        try:
            self.client.update_run(
                run_id=run_id,
                outputs=outputs or {},
                error=error or None,
                extra=extra,
                tags=tags,
                end_time=datetime.now(timezone.utc),
            )
        except Exception:
            return

    @staticmethod
    def _is_enabled() -> bool:
        raw = os.environ.get("ORCHESTRATOR_LANGSMITH_ENABLED")
        if raw is not None:
            return raw.strip().lower() not in {"0", "false", "no", ""}
        raw = os.environ.get("LANGSMITH_TRACING")
        if raw is not None:
            return raw.strip().lower() not in {"0", "false", "no", ""}
        return False


_TRACER: LangSmithTracer | None = None


def get_langsmith_tracer() -> LangSmithTracer:
    global _TRACER
    if _TRACER is None:
        _TRACER = LangSmithTracer()
    return _TRACER

