from __future__ import annotations

import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from backend.config import OrchestratorConfig
from backend.workers.base import Worker, WorkerControlCallback, WorkerProgressCallback
from backend.workers.claude_sdk_bridge import ClaudeSdkBridge
from backend.workers.models import WorkerArtifact, WorkerControlRef, WorkerProgressEvent, WorkerResult, WorkerSessionRef

try:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        HookMatcher,
        get_session_info,
        get_session_messages,
    )
    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
except ImportError:  # pragma: no cover - validated at runtime
    ClaudeAgentOptions = None
    ClaudeSDKClient = None
    HookMatcher = None
    PermissionResultAllow = None
    PermissionResultDeny = None
    ToolPermissionContext = None
    get_session_info = None
    get_session_messages = None


class ClaudeWorker(Worker):
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "claude"

    async def run(
        self,
        task: str,
        workspace: str,
        on_progress: WorkerProgressCallback | None = None,
        session_id: str | None = None,
        session_mode: str = "new",
        session_key: str = "primary",
        profile: str | None = None,
        on_control: WorkerControlCallback | None = None,
    ) -> WorkerResult:
        self._ensure_sdk_ready()
        workspace_path = Path(workspace or ".").resolve()
        before = self._snapshot_workspace(workspace_path)
        normalized_mode = self._normalize_session_mode(session_mode)
        normalized_profile = self._select_profile(profile)
        effective_session_id = (session_id or "").strip()

        if normalized_mode == "resume" and effective_session_id and on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"claude is resuming session ({effective_session_id[:8]})",
                    raw_type="session_resume",
                    metadata={
                        "worker": self.name,
                        "session_id": effective_session_id,
                        "session_key": session_key,
                        "session_mode": normalized_mode,
                        "worker_profile": normalized_profile,
                    },
                )
            )
        elif normalized_mode == "fork" and effective_session_id and on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"claude is forking session ({effective_session_id[:8]})",
                    raw_type="session_fork",
                    metadata={
                        "worker": self.name,
                        "session_id": effective_session_id,
                        "session_key": session_key,
                        "session_mode": normalized_mode,
                        "worker_profile": normalized_profile,
                    },
                )
            )
        elif on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message="claude is creating a new session",
                    raw_type="session_new",
                    metadata={
                        "worker": self.name,
                        "session_key": session_key,
                        "session_mode": normalized_mode,
                        "worker_profile": normalized_profile,
                    },
                )
            )

        stderr_chunks: list[str] = []
        raw_events: list[dict[str, Any]] = []
        final_text_parts: list[str] = []
        result_text = ""
        resolved_session_id = effective_session_id
        current_task_id = ""
        is_error = False
        result_errors: list[str] = []
        session_info_summary = ""
        mcp_status_summary = ""
        runtime_metadata: dict[str, Any] = {"worker_profile": normalized_profile}
        options = self._build_options(
            workspace=workspace_path,
            session_id=effective_session_id,
            session_mode=normalized_mode,
            profile=normalized_profile,
            stderr_chunks=stderr_chunks,
            raw_events=raw_events,
            on_progress=on_progress,
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                session_info_summary = await self._emit_server_info(client, on_progress, normalized_profile)
                mcp_status_summary = await self._emit_mcp_status(client, on_progress, normalized_profile)

                async def interrupt_active() -> dict[str, Any]:
                    await client.interrupt()
                    return {
                        "worker": self.name,
                        "session_id": resolved_session_id or effective_session_id,
                        "message": "Interrupt signal sent to Claude.",
                    }

                async def get_runtime_info() -> dict[str, Any]:
                    return {
                        "worker": self.name,
                        "session_id": resolved_session_id or effective_session_id,
                        "task_id": current_task_id,
                        "worker_profile": normalized_profile,
                        "session_info_summary": session_info_summary,
                        "mcp_status_summary": mcp_status_summary,
                    }

                if on_control:
                    await on_control(
                        WorkerControlRef(
                            worker=self.name,
                            session_id=resolved_session_id or effective_session_id or f"claude:{session_key}",
                            task_id=current_task_id,
                            can_interrupt=self.config.claude_enable_interrupt,
                            interrupt=interrupt_active if self.config.claude_enable_interrupt else None,
                            get_runtime_info=get_runtime_info,
                        )
                    )

                await client.query(task)
                async for message in client.receive_response():
                    raw_record = ClaudeSdkBridge.to_record(message)
                    raw_events.append(raw_record)
                    message_session_id = ClaudeSdkBridge.extract_session_id(message)
                    if message_session_id:
                        resolved_session_id = message_session_id

                    message_task_id = str(getattr(message, "task_id", "") or "").strip()
                    if message_task_id:
                        current_task_id = message_task_id
                        if on_control:
                            await on_control(
                                WorkerControlRef(
                                    worker=self.name,
                                    session_id=resolved_session_id or f"claude:{session_key}",
                                    task_id=current_task_id,
                                    can_interrupt=self.config.claude_enable_interrupt,
                                    interrupt=interrupt_active if self.config.claude_enable_interrupt else None,
                                    get_runtime_info=get_runtime_info,
                                )
                            )

                    extracted_text = ClaudeSdkBridge.extract_text(message)
                    if extracted_text:
                        final_text_parts.append(extracted_text)

                    if type(message).__name__ == "ResultMessage":
                        result_text = str(getattr(message, "result", "") or "").strip()
                        is_error = bool(getattr(message, "is_error", False))
                        result_errors = [str(item) for item in (getattr(message, "errors", None) or []) if item]

                    if on_progress:
                        for event in ClaudeSdkBridge.to_progress_events(message):
                            event.metadata.setdefault("worker", self.name)
                            event.metadata.setdefault("worker_profile", normalized_profile)
                            if current_task_id:
                                event.metadata.setdefault("task_id", current_task_id)
                            await on_progress(event)

                if self.config.claude_enable_session_introspection and resolved_session_id:
                    introspection = self._collect_session_introspection(resolved_session_id, workspace_path)
                    session_info_summary = introspection.get("session_info_summary", "") or session_info_summary
                    runtime_metadata.update(introspection)

        except Exception as error:
            after = self._snapshot_workspace(workspace_path)
            artifacts = self._diff_workspace(before, after)
            error_text = f"{error.__class__.__name__}: {error}"
            summary = self._build_summary(artifacts, result_text or "\n".join(final_text_parts), error_text=error_text)
            return WorkerResult(
                worker=self.name,
                success=False,
                summary=summary,
                output=result_text or "\n".join(final_text_parts).strip(),
                artifacts=artifacts,
                raw_events=raw_events,
                error=self._build_error_text(stderr_chunks, [error_text, *result_errors]),
                session=self._build_session_ref(
                    resolved_session_id,
                    session_key=session_key,
                    session_mode=normalized_mode,
                    continued_from=effective_session_id,
                ),
                metadata={
                    **runtime_metadata,
                    "session_info_summary": session_info_summary,
                    "mcp_status_summary": mcp_status_summary,
                },
            )
        finally:
            if on_control:
                await on_control(None)

        after = self._snapshot_workspace(workspace_path)
        artifacts = self._diff_workspace(before, after)
        output_text = result_text or "\n".join(part for part in final_text_parts if part).strip()
        error_text = self._build_error_text(stderr_chunks, result_errors)
        if is_error and not error_text and output_text:
            error_text = output_text
        summary = self._build_summary(artifacts, output_text, error_text=error_text if is_error else "")
        success = not is_error

        return WorkerResult(
            worker=self.name,
            success=success,
            summary=summary,
            output=output_text,
            artifacts=artifacts,
            raw_events=raw_events,
            error=error_text if not success else "",
            session=self._build_session_ref(
                resolved_session_id,
                session_key=session_key,
                session_mode=normalized_mode,
                continued_from=effective_session_id,
            ),
            metadata={
                **runtime_metadata,
                "session_info_summary": session_info_summary,
                "mcp_status_summary": mcp_status_summary,
            },
        )

    def _ensure_sdk_ready(self) -> None:
        if (
            ClaudeAgentOptions is None
            or ClaudeSDKClient is None
            or HookMatcher is None
            or PermissionResultAllow is None
            or PermissionResultDeny is None
        ):
            raise RuntimeError(
                "claude-agent-sdk is not available in the current Python environment. "
                "Install it with 'python -m pip install claude-agent-sdk' first."
            )

    def _build_options(
        self,
        *,
        workspace: Path,
        session_id: str,
        session_mode: str,
        profile: str,
        stderr_chunks: list[str],
        raw_events: list[dict[str, Any]],
        on_progress: WorkerProgressCallback | None,
    ) -> ClaudeAgentOptions:
        resume = session_id if session_mode in {"resume", "fork"} and session_id else None
        profile_rules = self._profile_rules(profile)
        allowed_tools = self._dedupe([*profile_rules["allowed"], *self.config.claude_allowed_tools])
        disallowed_tools = self._dedupe([*profile_rules["disallowed"], *self.config.claude_disallowed_tools])
        permission_mode = self.config.claude_permission_mode.strip() or None
        model = self.config.claude_model.strip() or None
        cli_path = self._resolve_command()
        settings_path = self._resolve_settings_path()
        mcp_servers = self._resolve_mcp_config()

        return ClaudeAgentOptions(
            cwd=str(workspace),
            cli_path=cli_path,
            model=model,
            permission_mode=permission_mode,
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            resume=resume,
            fork_session=session_mode == "fork",
            continue_conversation=session_mode == "resume" and bool(resume),
            include_partial_messages=False,
            setting_sources=["user"],
            settings=settings_path,
            stderr=lambda text: self._capture_stderr(stderr_chunks, text),
            hooks=self._build_hooks(raw_events=raw_events, on_progress=on_progress, profile=profile),
            can_use_tool=self._build_can_use_tool_handler(
                disallowed_tools=disallowed_tools,
                on_progress=on_progress,
                profile=profile,
            ),
            mcp_servers=mcp_servers,
            enable_file_checkpointing=self.config.claude_enable_file_checkpointing,
        )

    def _build_hooks(
        self,
        *,
        raw_events: list[dict[str, Any]],
        on_progress: WorkerProgressCallback | None,
        profile: str,
    ) -> dict[str, list[Any]] | None:
        if not self.config.claude_enable_hooks or HookMatcher is None:
            return None

        async def emit_hook(input_data: Any, tool_use_id: str | None, _context: Any) -> dict[str, Any]:
            hook_name = str(self._extract_hook_value(input_data, "hook_event_name") or "Hook").strip()
            tool_name = str(self._extract_hook_value(input_data, "tool_name") or "").strip()
            message = self._describe_hook_event(hook_name, tool_name)
            raw_events.append(
                {
                    "_type": "HookEvent",
                    "hook_event": hook_name,
                    "tool_name": tool_name,
                    "tool_use_id": tool_use_id,
                    "profile": profile,
                }
            )
            if on_progress:
                await on_progress(
                    ClaudeSdkBridge.build_hook_event(
                        hook_event=hook_name,
                        message=message,
                        tool_name=tool_name,
                        status="observed",
                        metadata={
                            "worker": self.name,
                            "worker_profile": profile,
                            "tool_use_id": tool_use_id,
                        },
                    )
                )
            return {}

        return {
            "UserPromptSubmit": [HookMatcher(hooks=[emit_hook])],
            "PreToolUse": [HookMatcher(hooks=[emit_hook])],
            "PostToolUse": [HookMatcher(hooks=[emit_hook])],
            "PostToolUseFailure": [HookMatcher(hooks=[emit_hook])],
            "Stop": [HookMatcher(hooks=[emit_hook])],
            "PermissionRequest": [HookMatcher(hooks=[emit_hook])],
        }

    def _build_can_use_tool_handler(
        self,
        *,
        disallowed_tools: list[str],
        on_progress: WorkerProgressCallback | None,
        profile: str,
    ) -> Callable[[str, dict[str, Any], ToolPermissionContext], Awaitable[Any]] | None:
        if PermissionResultAllow is None or PermissionResultDeny is None:
            return None

        explicit_allowed = {tool.lower() for tool in self.config.claude_allowed_tools}
        blocked = {tool.lower() for tool in disallowed_tools}

        async def can_use_tool(tool: str, tool_input: dict[str, Any], _context: ToolPermissionContext) -> Any:
            normalized_tool = (tool or "").strip().lower()
            if normalized_tool in blocked:
                message = f"Denied Claude tool {tool} under the {profile} profile."
                if on_progress:
                    await on_progress(
                        ClaudeSdkBridge.build_summary_event(
                            phase="worker_permission",
                            message=message,
                            metadata={
                                "worker": self.name,
                                "worker_profile": profile,
                                "permission_summary": message,
                                "tool_name": tool,
                            },
                        )
                    )
                return PermissionResultDeny(message=message, interrupt=False)

            if normalized_tool == "bash" and bool(tool_input.get("dangerouslyDisableSandbox")) and normalized_tool not in explicit_allowed:
                message = "Denied Claude request for unsandboxed Bash execution."
                if on_progress:
                    await on_progress(
                        ClaudeSdkBridge.build_summary_event(
                            phase="worker_permission",
                            message=message,
                            metadata={
                                "worker": self.name,
                                "worker_profile": profile,
                                "permission_summary": message,
                                "tool_name": tool,
                            },
                        )
                    )
                return PermissionResultDeny(message=message, interrupt=False)

            return PermissionResultAllow()

        return can_use_tool

    async def _emit_server_info(
        self,
        client: ClaudeSDKClient,
        on_progress: WorkerProgressCallback | None,
        profile: str,
    ) -> str:
        if not self.config.claude_enable_session_introspection:
            return ""
        try:
            server_info = await client.get_server_info()
        except Exception:
            return ""
        summary = self._summarize_server_info(server_info)
        if summary and on_progress:
            await on_progress(
                ClaudeSdkBridge.build_summary_event(
                    phase="worker_event",
                    message=summary,
                    metadata={
                        "worker": self.name,
                        "worker_profile": profile,
                        "session_info_summary": summary,
                        "server_info": server_info if isinstance(server_info, dict) else {"value": repr(server_info)},
                    },
                )
            )
        return summary

    async def _emit_mcp_status(
        self,
        client: ClaudeSDKClient,
        on_progress: WorkerProgressCallback | None,
        profile: str,
    ) -> str:
        try:
            status = await client.get_mcp_status()
        except Exception:
            return ""
        summary = self._summarize_mcp_status(status)
        if summary and on_progress:
            await on_progress(
                ClaudeSdkBridge.build_summary_event(
                    phase="worker_event",
                    message=summary,
                    metadata={
                        "worker": self.name,
                        "worker_profile": profile,
                        "mcp_status_summary": summary,
                        "mcp_status": status if isinstance(status, dict) else {"value": repr(status)},
                    },
                )
            )
        return summary

    def _collect_session_introspection(self, session_id: str, workspace: Path) -> dict[str, Any]:
        if get_session_info is None or get_session_messages is None:
            return {}
        session_info = None
        try:
            session_info = get_session_info(session_id, directory=str(workspace))
        except Exception:
            try:
                session_info = get_session_info(session_id)
            except Exception:
                session_info = None

        messages: list[Any] = []
        try:
            messages = get_session_messages(session_id, directory=str(workspace), limit=6)
        except Exception:
            try:
                messages = get_session_messages(session_id, limit=6)
            except Exception:
                messages = []

        summary = ""
        record: dict[str, Any] = {}
        if session_info is not None:
            info_dict = {
                "session_id": getattr(session_info, "session_id", ""),
                "summary": getattr(session_info, "summary", ""),
                "cwd": getattr(session_info, "cwd", ""),
                "git_branch": getattr(session_info, "git_branch", ""),
                "tag": getattr(session_info, "tag", ""),
            }
            record["session_info"] = info_dict
            raw_summary = str(info_dict.get("summary") or "").strip()
            if raw_summary:
                summary = f"Claude session info: {raw_summary[:220]}"

        if messages:
            simplified_messages: list[dict[str, Any]] = []
            for message in messages[-4:]:
                content = getattr(message, "message", None)
                simplified_messages.append(
                    {
                        "type": getattr(message, "type", ""),
                        "uuid": getattr(message, "uuid", ""),
                        "content_preview": self._message_preview(content),
                    }
                )
            record["recent_session_messages"] = simplified_messages
            if not summary:
                summary = f"Claude session has {len(messages)} recent message(s) available for inspection."

        if summary:
            record["session_info_summary"] = summary
        return record

    def _resolve_command(self) -> str | None:
        configured = self.config.claude_command.strip()
        if not configured:
            return None
        configured_path = Path(configured)
        if configured_path.exists():
            return str(configured_path)
        for candidate in (configured, f"{configured}.cmd", f"{configured}.bat", f"{configured}.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return configured

    def _resolve_settings_path(self) -> str | None:
        configured = self.config.claude_settings_path.strip()
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.exists():
                return str(candidate)
        default_path = Path.home() / ".claude" / "settings.json"
        if default_path.exists():
            return str(default_path)
        return None

    def _resolve_mcp_config(self) -> str | None:
        configured = self.config.claude_mcp_config.strip()
        if not configured:
            return None
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return str(candidate)
        return configured

    def _select_profile(self, requested_profile: str | None) -> str:
        normalized = (requested_profile or self.config.claude_profile_default or "code").strip().lower()
        return normalized if normalized in {"code", "doc", "study", "research"} else "code"

    @staticmethod
    def _normalize_session_mode(session_mode: str | None) -> str:
        normalized_mode = (session_mode or "new").strip().lower()
        return normalized_mode if normalized_mode in {"new", "resume", "fork"} else "new"

    @staticmethod
    def _profile_rules(profile: str) -> dict[str, list[str]]:
        if profile == "doc":
            return {"allowed": ["Read", "Write", "Edit", "LS", "Glob", "Grep"], "disallowed": ["Bash"]}
        if profile == "study":
            return {"allowed": ["Read", "Write", "Edit", "LS", "Glob", "Grep"], "disallowed": ["Bash"]}
        if profile == "research":
            return {
                "allowed": ["Read", "Write", "Edit", "LS", "Glob", "Grep", "WebFetch", "WebSearch"],
                "disallowed": ["Bash"],
            }
        return {"allowed": ["Read", "Write", "Edit", "LS", "Glob", "Grep", "Bash"], "disallowed": []}

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            normalized = str(item or "").strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    @staticmethod
    def _capture_stderr(stderr_chunks: list[str], text: str) -> None:
        normalized = str(text or "").strip()
        if normalized:
            stderr_chunks.append(normalized)

    @staticmethod
    def _build_session_ref(
        session_id: str,
        *,
        session_key: str,
        session_mode: str,
        continued_from: str,
    ) -> WorkerSessionRef | None:
        normalized = (session_id or "").strip()
        if not normalized:
            return None
        return WorkerSessionRef(
            worker="claude",
            session_id=normalized,
            session_key=session_key,
            mode=session_mode,
            continued_from=continued_from if session_mode in {"resume", "fork"} else "",
        )

    @staticmethod
    def _extract_hook_value(input_data: Any, key: str) -> Any:
        if isinstance(input_data, dict):
            return input_data.get(key)
        return getattr(input_data, key, None)

    @staticmethod
    def _describe_hook_event(hook_name: str, tool_name: str) -> str:
        if hook_name == "UserPromptSubmit":
            return "claude accepted a new user prompt for the active session"
        if hook_name == "PreToolUse":
            return f"claude is preparing to use {tool_name or 'a tool'}"
        if hook_name == "PostToolUse":
            return f"claude finished using {tool_name or 'a tool'}"
        if hook_name == "PostToolUseFailure":
            return f"claude saw a tool failure for {tool_name or 'a tool'}"
        if hook_name == "PermissionRequest":
            return f"claude requested permission for {tool_name or 'a tool'}"
        if hook_name == "Stop":
            return "claude reported a stop hook event"
        return f"claude hook event: {hook_name}"

    @staticmethod
    def _summarize_server_info(server_info: Any) -> str:
        if not isinstance(server_info, dict):
            return ""
        account = server_info.get("account") if isinstance(server_info.get("account"), dict) else {}
        models = server_info.get("models") if isinstance(server_info.get("models"), list) else []
        agents = server_info.get("agents") if isinstance(server_info.get("agents"), list) else []
        provider = str(account.get("apiProvider") or "").strip()
        if not provider and not models and not agents:
            return ""
        provider_text = f"provider={provider}" if provider else "provider=unknown"
        return f"Claude server info ready ({provider_text}, models={len(models)}, bundled agents={len(agents)})."

    @staticmethod
    def _summarize_mcp_status(status: Any) -> str:
        if not isinstance(status, dict):
            return ""
        servers = status.get("mcpServers")
        if not isinstance(servers, list):
            return ""
        if not servers:
            return "Claude MCP status: no MCP servers configured."
        names: list[str] = []
        for item in servers[:4]:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("serverName") or item.get("id") or "server").strip()
                names.append(name or "server")
            else:
                names.append(str(item))
        extra = len(servers) - len(names)
        suffix = f", and {extra} more" if extra > 0 else ""
        return "Claude MCP status: " + ", ".join(names) + suffix + "."

    @staticmethod
    def _message_preview(message: Any) -> str:
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content[:200]
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = str(block.get("text") or "").strip()
                    if text:
                        parts.append(text)
                    if len(" ".join(parts)) > 200:
                        break
                return " ".join(parts)[:200]
        return str(message)[:200]

    @staticmethod
    def _build_error_text(stderr_chunks: list[str], errors: list[str]) -> str:
        parts = [chunk.strip() for chunk in stderr_chunks if chunk.strip()]
        parts.extend(error.strip() for error in errors if error.strip())
        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            if part in seen:
                continue
            seen.add(part)
            deduped.append(part)
        return "\n".join(deduped).strip()

    @staticmethod
    def _snapshot_workspace(workspace: Path) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        if not workspace.exists():
            return snapshot
        for path in workspace.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            snapshot[str(path.relative_to(workspace)).replace("\\", "/")] = (stat.st_mtime_ns, stat.st_size)
        return snapshot

    @staticmethod
    def _diff_workspace(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[WorkerArtifact]:
        artifacts: list[WorkerArtifact] = []
        for path, (_, size) in after.items():
            if path not in before:
                artifacts.append(WorkerArtifact(path=path, change_type="created", size=size))
            elif before[path] != after[path]:
                artifacts.append(WorkerArtifact(path=path, change_type="modified", size=size))
        return sorted(artifacts, key=lambda item: (item.change_type, item.path))

    @staticmethod
    def _build_summary(
        artifacts: list[WorkerArtifact],
        output_text: str,
        *,
        error_text: str = "",
    ) -> str:
        parts: list[str] = []
        if artifacts:
            created = [artifact.path for artifact in artifacts if artifact.change_type == "created"]
            modified = [artifact.path for artifact in artifacts if artifact.change_type == "modified"]
            if created:
                parts.append("Created: " + ", ".join(created[:5]))
            if modified:
                parts.append("Modified: " + ", ".join(modified[:5]))
        if output_text:
            parts.append(output_text[:240])
        if error_text and not parts:
            parts.append(error_text[:240])
        if not parts:
            parts.append("claude finished without returning a summary")
        return " | ".join(parts)


