from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Python >=3.11 includes tomllib
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from backend.config import OrchestratorConfig
from backend.workers.base import Worker
from backend.workers.common import resolve_command, run_cli_worker
from backend.workers.models import WorkerProgressEvent, WorkerResult, WorkerSessionRef


class CodexWorker(Worker):
    _MCP_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
    _MCP_SERVER_ALLOWED_KEYS = {
        "args",
        "bearer_token_env_var",
        "command",
        "cwd",
        "default_tools_approval_mode",
        "disabled_tools",
        "enabled",
        "enabled_tools",
        "env",
        "env_http_headers",
        "env_vars",
        "experimental_environment",
        "http_headers",
        "oauth_resource",
        "required",
        "scopes",
        "startup_timeout_ms",
        "startup_timeout_sec",
        "supports_parallel_tool_calls",
        "tool_timeout_sec",
        "tools",
        "type",
        "url",
    }

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "codex"

    async def run(
        self,
        task: str,
        workspace: str,
        on_progress=None,
        session_id: str | None = None,
        session_mode: str = "new",
        session_key: str = "primary",
        profile: str | None = None,
        on_control=None,
    ) -> WorkerResult:
        executable = resolve_command(self.config.codex_command)
        workspace_path = Path(workspace or ".").resolve()
        command = [executable]
        if self.config.codex_model.strip():
            command.extend(["-m", self.config.codex_model.strip()])

        mcp_config_path = self._resolve_mcp_config()
        mcp_args, configured_servers, mcp_config_error = self._build_mcp_config_args(mcp_config_path)
        if mcp_args:
            command.extend(mcp_args)

        mcp_status, mcp_status_error = await self._query_mcp_status(executable=executable, mcp_args=mcp_args)
        mcp_status_summary = self._summarize_mcp_status(
            mcp_config_path=mcp_config_path,
            configured_servers=configured_servers,
            mcp_config_error=mcp_config_error,
            mcp_status=mcp_status,
            mcp_status_error=mcp_status_error,
        )

        if on_progress and mcp_status_summary:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_event",
                    message=mcp_status_summary,
                    raw_type="mcp_status",
                    metadata={
                        "worker": self.name,
                        "mcp_status_summary": mcp_status_summary,
                    },
                )
            )

        normalized_mode = (session_mode or "new").strip().lower()
        effective_session_id = (session_id or "").strip()
        if normalized_mode == "resume" and effective_session_id:
            command.extend(["exec", "resume", effective_session_id, "--skip-git-repo-check", task])
        else:
            command.extend(
                [
                    "-a",
                    "never",
                    "-s",
                    "workspace-write",
                    "-C",
                    str(workspace_path),
                    "exec",
                    "--skip-git-repo-check",
                    task,
                ]
            )
        result = await run_cli_worker(
            worker_name=self.name,
            command=command,
            workspace=str(workspace_path),
            task=task,
            on_progress=on_progress,
        )

        if mcp_status_summary:
            result.metadata["mcp_status_summary"] = mcp_status_summary
        if mcp_config_path:
            result.metadata["codex_mcp_config"] = mcp_config_path
        if mcp_status:
            result.metadata["mcp_servers"] = mcp_status
        if mcp_config_error:
            result.metadata["mcp_config_error"] = mcp_config_error
        if mcp_status_error:
            result.metadata["mcp_status_error"] = mcp_status_error

        if "command" in result.metadata and isinstance(result.metadata["command"], list):
            result.metadata["command"] = self._redact_mcp_config_args(result.metadata["command"])

        if effective_session_id:
            result.session = WorkerSessionRef(
                worker=self.name,
                session_id=effective_session_id,
                session_key=session_key,
                mode=normalized_mode,
                continued_from=effective_session_id if normalized_mode == "resume" else "",
            )
        return result

    def _resolve_mcp_config(self) -> str:
        configured = self.config.codex_mcp_config.strip()
        if not configured:
            return ""
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return str(candidate.resolve())
        return configured

    def _build_mcp_config_args(self, mcp_config_path: str) -> tuple[list[str], list[str], str]:
        if not mcp_config_path:
            return [], [], ""

        path = Path(mcp_config_path)
        if not path.exists() or not path.is_file():
            return [], [], f"MCP config file not found: {mcp_config_path}"

        try:
            loaded = self._load_mcp_config_data(path)
        except Exception as error:
            return [], [], f"MCP config parse failed ({error.__class__.__name__}: {error})"

        servers = self._extract_mcp_servers(loaded)
        if not servers:
            return [], [], ""

        args: list[str] = []
        for server_name, raw_server in servers.items():
            normalized_server = self._normalize_server_config(raw_server)
            for key, value in self._flatten_config(["mcp_servers", server_name], normalized_server):
                args.extend(["-c", f"{key}={self._to_toml_literal(value)}"])
        return args, list(servers.keys()), ""

    def _load_mcp_config_data(self, path: Path) -> dict[str, Any]:
        raw_text = path.read_text(encoding="utf-8-sig")
        suffix = path.suffix.lower()

        if suffix == ".json":
            loaded = json.loads(raw_text)
            return loaded if isinstance(loaded, dict) else {}

        if suffix == ".toml" and tomllib is not None:
            loaded = tomllib.loads(raw_text)
            return loaded if isinstance(loaded, dict) else {}

        try:
            loaded = json.loads(raw_text)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            if tomllib is None:
                raise
            loaded = tomllib.loads(raw_text)
            return loaded if isinstance(loaded, dict) else {}

    def _extract_mcp_servers(self, loaded: dict[str, Any]) -> dict[str, dict[str, Any]]:
        candidate = loaded.get("mcpServers")
        if isinstance(candidate, dict):
            return {str(name): dict(config) for name, config in candidate.items() if isinstance(config, dict)}

        candidate = loaded.get("mcp_servers")
        if isinstance(candidate, dict):
            return {str(name): dict(config) for name, config in candidate.items() if isinstance(config, dict)}

        # Support direct server mapping as a convenience.
        direct_servers: dict[str, dict[str, Any]] = {}
        for name, config in loaded.items():
            if not isinstance(config, dict):
                continue
            if any(key in config for key in ("command", "url", "transport", "type", "args")):
                direct_servers[str(name)] = dict(config)
        return direct_servers

    def _normalize_server_config(self, raw_server: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw_server)
        transport = normalized.pop("transport", None)
        if isinstance(transport, dict):
            for key, value in transport.items():
                normalized.setdefault(str(key), value)

        # Claude-style configs often use `headers`; Codex expects `http_headers`.
        headers = normalized.pop("headers", None)
        if headers is not None and "http_headers" not in normalized:
            normalized["http_headers"] = headers

        return {
            key: value
            for key, value in normalized.items()
            if key in self._MCP_SERVER_ALLOWED_KEYS and value is not None
        }

    def _flatten_config(self, path: list[str], value: Any) -> list[tuple[str, Any]]:
        if value is None:
            return []

        if isinstance(value, dict):
            items: list[tuple[str, Any]] = []
            for key, item in value.items():
                if item is None:
                    continue
                items.extend(self._flatten_config([*path, str(key)], item))
            return items

        key = ".".join(self._format_key_segment(segment=segment) for segment in path)
        return [(key, value)]

    def _format_key_segment(self, *, segment: str) -> str:
        if self._MCP_SEGMENT_PATTERN.fullmatch(segment):
            return segment
        return json.dumps(segment, ensure_ascii=False)

    async def _query_mcp_status(
        self,
        *,
        executable: str,
        mcp_args: list[str],
    ) -> tuple[list[dict[str, Any]] | None, str]:
        status_command = [executable, *mcp_args, "mcp", "list", "--json"]
        try:
            process = await asyncio.create_subprocess_exec(
                *status_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_raw, stderr_raw = await process.communicate()
        except Exception as error:
            return None, f"Failed to query Codex MCP status ({error.__class__.__name__}: {error})"

        stdout_text = stdout_raw.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_raw.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            detail = stderr_text or stdout_text or f"exit code {process.returncode}"
            return None, f"Codex MCP status command failed: {detail}"

        if not stdout_text:
            return [], ""

        try:
            loaded = json.loads(stdout_text)
        except json.JSONDecodeError as error:
            return None, f"Codex MCP status parsing failed ({error.__class__.__name__}: {error})"

        if isinstance(loaded, list):
            return [dict(item) for item in loaded if isinstance(item, dict)], ""
        if isinstance(loaded, dict):
            servers = loaded.get("servers")
            if isinstance(servers, list):
                return [dict(item) for item in servers if isinstance(item, dict)], ""
        return [], ""

    def _summarize_mcp_status(
        self,
        *,
        mcp_config_path: str,
        configured_servers: list[str],
        mcp_config_error: str,
        mcp_status: list[dict[str, Any]] | None,
        mcp_status_error: str,
    ) -> str:
        if mcp_config_error:
            return f"Codex MCP status: {mcp_config_error}."

        if mcp_status is not None:
            if not mcp_status:
                if mcp_config_path:
                    return "Codex MCP status: no MCP servers enabled for this run."
                return "Codex MCP status: no MCP servers configured."
            names: list[str] = []
            for item in mcp_status[:4]:
                name = str(item.get("name") or item.get("id") or "").strip()
                if name:
                    names.append(name)
            if not names:
                names = ["server"] * min(len(mcp_status), 4)
            extra = len(mcp_status) - len(names)
            suffix = f", and {extra} more" if extra > 0 else ""
            return "Codex MCP status: " + ", ".join(names) + suffix + "."

        if configured_servers:
            listed = ", ".join(configured_servers[:4])
            extra = len(configured_servers) - min(len(configured_servers), 4)
            suffix = f", and {extra} more" if extra > 0 else ""
            if mcp_status_error:
                return f"Codex MCP status: configured ({listed}{suffix}), but status query failed."
            return f"Codex MCP status: configured ({listed}{suffix})."

        if mcp_config_path and mcp_status_error:
            return f"Codex MCP status: {mcp_status_error}."

        return ""

    def _redact_mcp_config_args(self, command: list[Any]) -> list[Any]:
        redacted: list[Any] = []
        for index, part in enumerate(command):
            text = str(part)
            if index > 0 and str(command[index - 1]) == "-c" and (
                ".env." in text or ".http_headers." in text or ".headers." in text
            ):
                key = text.split("=", 1)[0]
                redacted.append(f"{key}=***")
                continue
            redacted.append(part)
        return redacted

    @staticmethod
    def _to_toml_literal(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return repr(value)
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, list):
            return "[" + ", ".join(CodexWorker._to_toml_literal(item) for item in value) + "]"
        if isinstance(value, dict):
            entries: list[str] = []
            for key, item in value.items():
                normalized_key = str(key)
                if CodexWorker._MCP_SEGMENT_PATTERN.fullmatch(normalized_key):
                    key_literal = normalized_key
                else:
                    key_literal = json.dumps(normalized_key, ensure_ascii=False)
                entries.append(f"{key_literal} = {CodexWorker._to_toml_literal(item)}")
            return "{ " + ", ".join(entries) + " }"
        return json.dumps(str(value), ensure_ascii=False)


