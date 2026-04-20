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
class MemoryConfig:
    enabled: bool = True
    auto_compact: bool = True
    compact_on_complete: bool = True
    compact_on_failure: bool = True
    retrieval_scope: str = "global"
    retrieval_strength: str = "standard"
    cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24


@dataclass(slots=True)
class OrchestratorConfig:
    planner: PlannerConfig
    memory: MemoryConfig
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


def read_config_data() -> dict[str, object]:
    path = _config_path()
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return {}


def write_config_data(data: dict[str, object]) -> None:
    path = _config_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_planner_config(*, provider: str, model: str, api_key: str, api_base: str) -> None:
    data = read_config_data()
    planner = data.get("planner")
    planner_data = planner if isinstance(planner, dict) else {}
    planner_data["provider"] = provider
    planner_data["model"] = model
    planner_data["apiKey"] = api_key
    planner_data["apiBase"] = api_base
    data["planner"] = planner_data
    write_config_data(data)


def update_memory_config(
    *,
    enabled: bool,
    auto_compact: bool,
    compact_on_complete: bool,
    compact_on_failure: bool,
    retrieval_scope: str,
    retrieval_strength: str,
    cleanup_enabled: bool,
    cleanup_interval_hours: int,
) -> None:
    data = read_config_data()
    memory = data.get("memory")
    memory_data = memory if isinstance(memory, dict) else {}
    memory_data["enabled"] = enabled
    memory_data["autoCompact"] = auto_compact
    memory_data["compactOnComplete"] = compact_on_complete
    memory_data["compactOnFailure"] = compact_on_failure
    memory_data["retrievalScope"] = retrieval_scope
    memory_data["retrievalStrength"] = retrieval_strength
    memory_data["cleanupEnabled"] = cleanup_enabled
    memory_data["cleanupIntervalHours"] = cleanup_interval_hours
    data["memory"] = memory_data
    write_config_data(data)


def get_runtime_config_view() -> dict[str, object]:
    config = load_config()
    return {
        "planner": {
            "provider": config.planner.provider,
            "model": config.planner.model,
            "apiKey": config.planner.api_key,
            "apiBase": config.planner.api_base,
        },
        "memory": {
            "enabled": config.memory.enabled,
            "autoCompact": config.memory.auto_compact,
            "compactOnComplete": config.memory.compact_on_complete,
            "compactOnFailure": config.memory.compact_on_failure,
            "retrievalScope": config.memory.retrieval_scope,
            "retrievalStrength": config.memory.retrieval_strength,
            "cleanupEnabled": config.memory.cleanup_enabled,
            "cleanupIntervalHours": config.memory.cleanup_interval_hours,
        },
    }


def load_config() -> OrchestratorConfig:
    data: dict[str, object] = read_config_data()

    planner_data = data.get("planner") if isinstance(data, dict) else {}
    planner_dict = planner_data if isinstance(planner_data, dict) else {}
    memory_data = data.get("memory") if isinstance(data, dict) else {}
    memory_dict = memory_data if isinstance(memory_data, dict) else {}
    planner = PlannerConfig(
        provider=os.environ.get("ORCHESTRATOR_PROVIDER", str(planner_dict.get("provider") or "openai_compat")),
        model=os.environ.get("ORCHESTRATOR_MODEL", str(planner_dict.get("model") or "")),
        api_key=os.environ.get("ORCHESTRATOR_API_KEY", str(planner_dict.get("apiKey") or "")),
        api_base=os.environ.get("ORCHESTRATOR_API_BASE", str(planner_dict.get("apiBase") or "")),
        temperature=float(os.environ.get("ORCHESTRATOR_TEMPERATURE", planner_dict.get("temperature") or 0.2)),
        max_tokens=int(os.environ.get("ORCHESTRATOR_MAX_TOKENS", planner_dict.get("maxTokens") or 4096)),
    )
    memory = MemoryConfig(
        enabled=str(os.environ.get("ORCHESTRATOR_MEMORY_ENABLED", memory_dict.get("enabled", True))).strip().lower()
        not in {"0", "false", "no", ""},
        auto_compact=str(os.environ.get("ORCHESTRATOR_MEMORY_AUTO_COMPACT", memory_dict.get("autoCompact", True)))
        .strip()
        .lower()
        not in {"0", "false", "no", ""},
        compact_on_complete=str(
            os.environ.get("ORCHESTRATOR_MEMORY_COMPACT_ON_COMPLETE", memory_dict.get("compactOnComplete", True))
        )
        .strip()
        .lower()
        not in {"0", "false", "no", ""},
        compact_on_failure=str(
            os.environ.get("ORCHESTRATOR_MEMORY_COMPACT_ON_FAILURE", memory_dict.get("compactOnFailure", True))
        )
        .strip()
        .lower()
        not in {"0", "false", "no", ""},
        retrieval_scope=str(
            os.environ.get("ORCHESTRATOR_MEMORY_RETRIEVAL_SCOPE", memory_dict.get("retrievalScope") or "global")
        ),
        retrieval_strength=str(
            os.environ.get(
                "ORCHESTRATOR_MEMORY_RETRIEVAL_STRENGTH",
                memory_dict.get("retrievalStrength") or "standard",
            )
        ),
        cleanup_enabled=str(
            os.environ.get("ORCHESTRATOR_MEMORY_CLEANUP_ENABLED", memory_dict.get("cleanupEnabled", True))
        )
        .strip()
        .lower()
        not in {"0", "false", "no", ""},
        cleanup_interval_hours=int(
            os.environ.get(
                "ORCHESTRATOR_MEMORY_CLEANUP_INTERVAL_HOURS",
                memory_dict.get("cleanupIntervalHours") or 24,
            )
        ),
    )
    return OrchestratorConfig(
        planner=planner,
        memory=memory,
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

