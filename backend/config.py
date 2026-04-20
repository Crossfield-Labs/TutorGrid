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
    opencode_model: str = ""
    opencode_agent: str = ""
    codex_command: str = "codex"
    codex_model: str = ""
    claude_command: str = "claude"
    claude_sdk_enabled: bool = True
    claude_model: str = ""
    claude_permission_mode: str = "acceptEdits"
    claude_allowed_tools: list[str] = field(default_factory=list)
    claude_disallowed_tools: list[str] = field(default_factory=list)
    claude_settings_path: str = ""
    claude_mcp_config: str = ""
    claude_profile_default: str = "code"
    claude_enable_interrupt: bool = True
    claude_enable_hooks: bool = True
    claude_enable_session_introspection: bool = True
    claude_enable_file_checkpointing: bool = False
    opencode_command: str = "opencode"
    enabled_workers: list[str] = field(default_factory=lambda: ["codex", "claude", "opencode"])


def _config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config.json"


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
        opencode_model=str(os.environ.get("ORCHESTRATOR_OPENCODE_MODEL", data.get("opencodeModel") or "")),
        opencode_agent=str(os.environ.get("ORCHESTRATOR_OPENCODE_AGENT", data.get("opencodeAgent") or "")),
        codex_command=os.environ.get("ORCHESTRATOR_CODEX_COMMAND", str(data.get("codexCommand") or "codex")),
        codex_model=str(os.environ.get("ORCHESTRATOR_CODEX_MODEL", data.get("codexModel") or "")),
        claude_command=os.environ.get("ORCHESTRATOR_CLAUDE_COMMAND", str(data.get("claudeCommand") or "claude")),
        claude_sdk_enabled=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_SDK_ENABLED", data.get("claudeSdkEnabled", True))
        ).strip().lower()
        not in {"0", "false", "no", ""},
        claude_model=str(os.environ.get("ORCHESTRATOR_CLAUDE_MODEL", data.get("claudeModel") or "")),
        claude_permission_mode=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_PERMISSION_MODE", data.get("claudePermissionMode") or "acceptEdits")
        ),
        claude_allowed_tools=[
            item.strip()
            for item in os.environ.get(
                "ORCHESTRATOR_CLAUDE_ALLOWED_TOOLS",
                ",".join(data.get("claudeAllowedTools") or []),
            ).split(",")
            if item.strip()
        ],
        claude_disallowed_tools=[
            item.strip()
            for item in os.environ.get(
                "ORCHESTRATOR_CLAUDE_DISALLOWED_TOOLS",
                ",".join(data.get("claudeDisallowedTools") or []),
            ).split(",")
            if item.strip()
        ],
        claude_settings_path=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_SETTINGS_PATH", data.get("claudeSettingsPath") or "")
        ),
        claude_mcp_config=str(os.environ.get("ORCHESTRATOR_CLAUDE_MCP_CONFIG", data.get("claudeMcpConfig") or "")),
        claude_profile_default=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_PROFILE_DEFAULT", data.get("claudeProfileDefault") or "code")
        ),
        claude_enable_interrupt=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_ENABLE_INTERRUPT", data.get("claudeEnableInterrupt", True))
        ).strip().lower()
        not in {"0", "false", "no", ""},
        claude_enable_hooks=str(
            os.environ.get("ORCHESTRATOR_CLAUDE_ENABLE_HOOKS", data.get("claudeEnableHooks", True))
        ).strip().lower()
        not in {"0", "false", "no", ""},
        claude_enable_session_introspection=str(
            os.environ.get(
                "ORCHESTRATOR_CLAUDE_ENABLE_SESSION_INTROSPECTION",
                data.get("claudeEnableSessionIntrospection", True),
            )
        ).strip().lower()
        not in {"0", "false", "no", ""},
        claude_enable_file_checkpointing=str(
            os.environ.get(
                "ORCHESTRATOR_CLAUDE_ENABLE_FILE_CHECKPOINTING",
                data.get("claudeEnableFileCheckpointing", False),
            )
        ).strip().lower()
        in {"1", "true", "yes"},
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

