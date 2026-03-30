from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from config.subagent_config import SubAgentConfig
from workers.base import WorkerAdapter, WorkerProgressCallback
from workers.claude_sdk_bridge import ClaudeSdkBridge
from workers.models import WorkerArtifact, WorkerProgressEvent, WorkerResult, WorkerSessionRef

try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
except ImportError:  # pragma: no cover - validated at runtime
    ClaudeAgentOptions = None
    ClaudeSDKClient = None


class ClaudeSdkWorker(WorkerAdapter):
    def __init__(self, config: SubAgentConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "claude"

    @property
    def description(self) -> str:
        return "Delegate broader agentic coding, documentation, or analysis work to the local Claude Agent SDK."

    async def run(
        self,
        *,
        task: str,
        workspace: str,
        on_progress: WorkerProgressCallback | None = None,
        session_id: str | None = None,
        session_mode: str = "new",
        session_key: str = "primary",
    ) -> WorkerResult:
        self._ensure_sdk_ready()
        workspace_path = Path(workspace or ".").resolve()
        before = self._snapshot_workspace(workspace_path)
        normalized_mode = (session_mode or "new").strip().lower()
        effective_session_id = (session_id or "").strip()
        if normalized_mode not in {"new", "resume", "fork"}:
            normalized_mode = "new"

        if normalized_mode == "resume" and effective_session_id and on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"claude is resuming session ({effective_session_id[:8]})",
                    raw_type="session_resume",
                    metadata={"session_id": effective_session_id, "session_key": session_key},
                )
            )
        elif normalized_mode == "fork" and effective_session_id and on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"claude is forking session ({effective_session_id[:8]})",
                    raw_type="session_fork",
                    metadata={"session_id": effective_session_id, "session_key": session_key},
                )
            )
        elif on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message="claude is creating a new session",
                    raw_type="session_new",
                    metadata={"session_key": session_key},
                )
            )

        stderr_chunks: list[str] = []
        options = self._build_options(
            workspace=workspace_path,
            session_id=effective_session_id,
            session_mode=normalized_mode,
            stderr_chunks=stderr_chunks,
        )

        raw_events: list[dict[str, Any]] = []
        final_text_parts: list[str] = []
        result_text = ""
        resolved_session_id = effective_session_id
        is_error = False
        result_errors: list[str] = []

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(task)
                async for message in client.receive_response():
                    raw_record = ClaudeSdkBridge.to_record(message)
                    raw_events.append(raw_record)
                    message_session_id = ClaudeSdkBridge.extract_session_id(message)
                    if message_session_id:
                        resolved_session_id = message_session_id

                    extracted_text = ClaudeSdkBridge.extract_text(message)
                    if extracted_text:
                        final_text_parts.append(extracted_text)

                    if type(message).__name__ == "ResultMessage":
                        result_text = str(getattr(message, "result", "") or "").strip()
                        is_error = bool(getattr(message, "is_error", False))
                        result_errors = [str(item) for item in (getattr(message, "errors", None) or []) if item]

                    if on_progress:
                        for event in ClaudeSdkBridge.to_progress_events(message):
                            await on_progress(event)
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
            )

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
        )

    def _ensure_sdk_ready(self) -> None:
        if ClaudeAgentOptions is None or ClaudeSDKClient is None:
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
        stderr_chunks: list[str],
    ) -> ClaudeAgentOptions:
        resume = session_id if session_mode in {"resume", "fork"} and session_id else None
        allowed_tools = list(self.config.claude_allowed_tools)
        permission_mode = self.config.claude_permission_mode.strip() or None
        model = self.config.claude_model.strip() or None
        cli_path = self._resolve_command()
        settings_path = self._resolve_settings_path()

        return ClaudeAgentOptions(
            cwd=str(workspace),
            cli_path=cli_path,
            model=model,
            permission_mode=permission_mode,
            allowed_tools=allowed_tools,
            resume=resume,
            fork_session=session_mode == "fork",
            continue_conversation=session_mode == "resume" and bool(resume),
            include_partial_messages=False,
            setting_sources=["user"],
            settings=settings_path,
            stderr=lambda text: self._capture_stderr(stderr_chunks, text),
        )

    def _resolve_command(self) -> str | None:
        configured = self.config.claude_command.strip()
        if not configured:
            return None

        configured_path = Path(configured)
        if configured_path.exists():
            return str(configured_path)

        for candidate in (
            configured,
            f"{configured}.cmd",
            f"{configured}.bat",
            f"{configured}.exe",
        ):
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
    def _diff_workspace(
        before: dict[str, tuple[int, int]],
        after: dict[str, tuple[int, int]],
    ) -> list[WorkerArtifact]:
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
