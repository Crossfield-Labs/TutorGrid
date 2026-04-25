from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.config import load_config


class LangSmithTracer:
    def __init__(self) -> None:
        config = load_config()
        self.enabled = config.langsmith.enabled
        self.project_name = config.langsmith.project or "pc-orchestrator-core"
        self.api_key = config.langsmith.api_key
        self.api_url = config.langsmith.api_url
        self.client = None
        if not self.enabled:
            return
        try:
            from langsmith import Client

            client_kwargs: dict[str, str] = {}
            if self.api_key:
                client_kwargs["api_key"] = self.api_key
            if self.api_url:
                client_kwargs["api_url"] = self.api_url
            self.client = Client(**client_kwargs)
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


_TRACER: LangSmithTracer | None = None


def get_langsmith_tracer() -> LangSmithTracer:
    global _TRACER
    if _TRACER is None:
        _TRACER = LangSmithTracer()
    return _TRACER


def reset_langsmith_tracer() -> None:
    global _TRACER
    _TRACER = None

