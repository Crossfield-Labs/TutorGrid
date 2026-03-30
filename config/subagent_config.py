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
class SubAgentConfig:
    planner: PlannerConfig
    max_iterations: int = 16
    shell_timeout_seconds: int = 90
    opencode_command: str = "opencode"
    opencode_model: str = ""
    opencode_agent: str = ""
    codex_command: str = "codex"
    codex_model: str = ""
    claude_sdk_enabled: bool = True
    claude_command: str = "claude"
    claude_model: str = ""
    claude_permission_mode: str = "acceptEdits"
    claude_allowed_tools: list[str] = field(default_factory=list)
    claude_settings_path: str = ""


def _config_path() -> Path:
    return Path(__file__).resolve().parent / "subagent_config.json"


def _parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


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
        max_iterations=int(os.environ.get("METAAGENT_SUBAGENT_MAX_ITERATIONS", data.get("maxIterations") or 16)),
        shell_timeout_seconds=int(
            os.environ.get("METAAGENT_SUBAGENT_SHELL_TIMEOUT", data.get("shellTimeoutSeconds") or 90)
        ),
        opencode_command=os.environ.get(
            "METAAGENT_SUBAGENT_OPENCODE_COMMAND",
            str(data.get("opencodeCommand") or "opencode"),
        ),
        opencode_model=os.environ.get("METAAGENT_SUBAGENT_OPENCODE_MODEL", str(data.get("opencodeModel") or "")),
        opencode_agent=os.environ.get("METAAGENT_SUBAGENT_OPENCODE_AGENT", str(data.get("opencodeAgent") or "")),
        codex_command=os.environ.get("METAAGENT_SUBAGENT_CODEX_COMMAND", str(data.get("codexCommand") or "codex")),
        codex_model=os.environ.get("METAAGENT_SUBAGENT_CODEX_MODEL", str(data.get("codexModel") or "")),
        claude_sdk_enabled=_parse_bool(
            os.environ.get("METAAGENT_SUBAGENT_CLAUDE_SDK_ENABLED", data.get("claudeSdkEnabled")),
            True,
        ),
        claude_command=os.environ.get(
            "METAAGENT_SUBAGENT_CLAUDE_COMMAND",
            str(data.get("claudeCommand") or "claude"),
        ),
        claude_model=os.environ.get("METAAGENT_SUBAGENT_CLAUDE_MODEL", str(data.get("claudeModel") or "")),
        claude_permission_mode=os.environ.get(
            "METAAGENT_SUBAGENT_CLAUDE_PERMISSION_MODE",
            str(data.get("claudePermissionMode") or "acceptEdits"),
        ),
        claude_allowed_tools=_parse_str_list(
            os.environ.get("METAAGENT_SUBAGENT_CLAUDE_ALLOWED_TOOLS", data.get("claudeAllowedTools"))
        ),
        claude_settings_path=os.environ.get(
            "METAAGENT_SUBAGENT_CLAUDE_SETTINGS",
            str(data.get("claudeSettingsPath") or ""),
        ),
    )
