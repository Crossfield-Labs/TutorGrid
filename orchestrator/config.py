from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PlannerConfig:
    provider: str = "openai_compat"
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass(slots=True)
class OrchestratorConfig:
    planner: PlannerConfig
    max_iterations: int = 8
    shell_timeout_seconds: int = 90
    codex_command: str = "codex"
    claude_command: str = "claude"
    opencode_command: str = "opencode"
    enabled_workers: list[str] = field(default_factory=lambda: ["codex", "claude", "opencode"])


def _config_path() -> Path:
    return Path(__file__).resolve().parent / "config.json"


def load_config() -> OrchestratorConfig:
    data: dict[str, object] = {}
    path = _config_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))

    planner_data = data.get("planner") if isinstance(data, dict) else {}
    planner_dict = planner_data if isinstance(planner_data, dict) else {}
    planner = PlannerConfig(
        provider=os.environ.get("ORCHESTRATOR_PROVIDER", str(planner_dict.get("provider") or "openai_compat")),
        model=os.environ.get("ORCHESTRATOR_MODEL", str(planner_dict.get("model") or "")),
        api_key=os.environ.get("ORCHESTRATOR_API_KEY", str(planner_dict.get("apiKey") or "")),
        api_base=os.environ.get("ORCHESTRATOR_API_BASE", str(planner_dict.get("apiBase") or "")),
        temperature=float(os.environ.get("ORCHESTRATOR_TEMPERATURE", planner_dict.get("temperature") or 0.2)),
        max_tokens=int(os.environ.get("ORCHESTRATOR_MAX_TOKENS", planner_dict.get("maxTokens") or 4096)),
    )
    return OrchestratorConfig(
        planner=planner,
        max_iterations=int(os.environ.get("ORCHESTRATOR_MAX_ITERATIONS", data.get("maxIterations") or 8)),
        shell_timeout_seconds=int(os.environ.get("ORCHESTRATOR_SHELL_TIMEOUT", data.get("shellTimeoutSeconds") or 90)),
        codex_command=os.environ.get("ORCHESTRATOR_CODEX_COMMAND", str(data.get("codexCommand") or "codex")),
        claude_command=os.environ.get("ORCHESTRATOR_CLAUDE_COMMAND", str(data.get("claudeCommand") or "claude")),
        opencode_command=os.environ.get("ORCHESTRATOR_OPENCODE_COMMAND", str(data.get("opencodeCommand") or "opencode")),
        enabled_workers=[
            item.strip()
            for item in os.environ.get(
                "ORCHESTRATOR_ENABLED_WORKERS",
                ",".join(data.get("enabledWorkers") or ["codex", "claude", "opencode"]),
            ).split(",")
            if item.strip()
        ],
    )
