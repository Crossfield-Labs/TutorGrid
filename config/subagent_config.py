from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
class SubAgentConfig:
    planner: PlannerConfig
    max_iterations: int = 12
    shell_timeout_seconds: int = 90
    opencode_command: str = "opencode"
    opencode_model: str = ""
    opencode_agent: str = ""


def _config_path() -> Path:
    return Path(__file__).resolve().parent / "subagent_config.json"


def load_subagent_config() -> SubAgentConfig:
    data: dict[str, object] = {}
    path = _config_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))

    planner_data = data.get("planner") if isinstance(data, dict) else {}
    planner_dict = planner_data if isinstance(planner_data, dict) else {}
    planner = PlannerConfig(
        provider=os.environ.get("METAAGENT_SUBAGENT_PROVIDER", str(planner_dict.get("provider") or "openai_compat")),
        model=os.environ.get("METAAGENT_SUBAGENT_MODEL", str(planner_dict.get("model") or "")),
        api_key=os.environ.get("METAAGENT_SUBAGENT_API_KEY", str(planner_dict.get("apiKey") or "")),
        api_base=os.environ.get("METAAGENT_SUBAGENT_API_BASE", str(planner_dict.get("apiBase") or "")),
        temperature=float(os.environ.get("METAAGENT_SUBAGENT_TEMPERATURE", planner_dict.get("temperature") or 0.2)),
        max_tokens=int(os.environ.get("METAAGENT_SUBAGENT_MAX_TOKENS", planner_dict.get("maxTokens") or 4096)),
    )
    return SubAgentConfig(
        planner=planner,
        max_iterations=int(os.environ.get("METAAGENT_SUBAGENT_MAX_ITERATIONS", data.get("maxIterations") or 12)),
        shell_timeout_seconds=int(
            os.environ.get("METAAGENT_SUBAGENT_SHELL_TIMEOUT", data.get("shellTimeoutSeconds") or 90)
        ),
        opencode_command=os.environ.get("METAAGENT_SUBAGENT_OPENCODE_COMMAND", str(data.get("opencodeCommand") or "opencode")),
        opencode_model=os.environ.get("METAAGENT_SUBAGENT_OPENCODE_MODEL", str(data.get("opencodeModel") or "")),
        opencode_agent=os.environ.get("METAAGENT_SUBAGENT_OPENCODE_AGENT", str(data.get("opencodeAgent") or "")),
    )
