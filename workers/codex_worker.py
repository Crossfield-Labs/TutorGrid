from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from config.subagent_config import SubAgentConfig
from workers.base import WorkerAdapter, WorkerProgressCallback
from workers.models import WorkerArtifact, WorkerProgressEvent, WorkerResult, WorkerSessionRef


class CodexWorker(WorkerAdapter):
    def __init__(self, config: SubAgentConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "codex"

    @property
    def description(self) -> str:
        return "Delegate coding or analysis work to the local Codex CLI."

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
        workspace_path = Path(workspace or ".").resolve()
        before = self._snapshot_workspace(workspace_path)
        normalized_mode = (session_mode or "new").strip().lower()
        effective_session_id = (session_id or "").strip()

        if normalized_mode == "fork":
            if on_progress:
                await on_progress(
                    WorkerProgressEvent(
                        phase="worker_session",
                        message="codex non-interactive fork is not wired yet, so a fresh session will be created instead.",
                        raw_type="session_fallback",
                        metadata={"requested_mode": session_mode, "session_id": effective_session_id},
                    )
                )
            normalized_mode = "new"
            effective_session_id = ""

        if normalized_mode == "resume" and effective_session_id and on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message=f"codex is resuming session ({effective_session_id[:8]})",
                    raw_type="session_resume",
                    metadata={"session_id": effective_session_id, "session_key": session_key},
                )
            )
        elif on_progress:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session",
                    message="codex is creating a new session",
                    raw_type="session_new",
                    metadata={"session_key": session_key},
                )
            )

        command = self._build_command(
            task,
            workspace_path,
            session_id=effective_session_id,
            session_mode=normalized_mode,
        )

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_path),
        )

        stdout_task = asyncio.create_task(self._consume_stdout(process.stdout, on_progress))
        stderr_task = asyncio.create_task(self._consume_stderr(process.stderr))
        stdout_lines, raw_events = await stdout_task
        stderr = await stderr_task
        returncode = await process.wait()

        after = self._snapshot_workspace(workspace_path)
        artifacts = self._diff_workspace(before, after)
        final_message = self._extract_final_message(raw_events)
        resolved_session_id = self._extract_thread_id(raw_events) or effective_session_id
        session_ref = (
            WorkerSessionRef(
                worker=self.name,
                session_id=resolved_session_id,
                session_key=session_key,
                mode=normalized_mode,
                continued_from=effective_session_id if normalized_mode == "resume" else "",
            )
            if resolved_session_id
            else None
        )
        summary = self._build_summary(artifacts, final_message, returncode)
        if returncode != 0:
            error_text = stderr or final_message or f"codex exited with code {returncode}"
            return WorkerResult(
                worker=self.name,
                success=False,
                summary=summary,
                output=final_message,
                artifacts=artifacts,
                raw_events=raw_events,
                error=error_text,
                session=session_ref,
            )

        return WorkerResult(
            worker=self.name,
            success=True,
            summary=summary,
            output=final_message or "\n".join(stdout_lines[-20:]),
            artifacts=artifacts,
            raw_events=raw_events,
            session=session_ref,
        )

    def _build_command(
        self,
        task: str,
        workspace: Path,
        *,
        session_id: str,
        session_mode: str,
    ) -> list[str]:
        executable = self._resolve_command()
        command: list[str] = [executable]
        model = self.config.codex_model.strip()
        if model:
            command.extend(["-m", model])
        if session_mode == "resume" and session_id:
            command.extend(
                [
                    "exec",
                    "resume",
                    session_id,
                    "--json",
                    "--skip-git-repo-check",
                ]
            )
        else:
            command.extend(
                [
                    "-a",
                    "never",
                    "-s",
                    "workspace-write",
                    "-C",
                    str(workspace),
                    "exec",
                    "--json",
                    "--skip-git-repo-check",
                ]
            )
        command.append(task)
        return command

    def _resolve_command(self) -> str:
        configured = self.config.codex_command.strip()
        if not configured:
            raise RuntimeError("codex command is not configured.")

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
        raise FileNotFoundError(f"Unable to locate codex command: {configured}")

    async def _consume_stdout(
        self,
        stream: asyncio.StreamReader | None,
        on_progress: WorkerProgressCallback | None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if stream is None:
            return [], []

        lines: list[str] = []
        raw_events: list[dict[str, Any]] = []
        async for raw_line in stream:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            lines.append(line)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None

            if isinstance(payload, dict):
                raw_events.append(payload)
                if on_progress:
                    await on_progress(self._translate_event(payload))
            elif on_progress:
                await on_progress(
                    WorkerProgressEvent(
                        phase="worker_output",
                        message=f"codex output: {line[:200]}",
                        raw_type="raw",
                        detail=line[:400],
                    )
                )
        return lines, raw_events

    @staticmethod
    async def _consume_stderr(stream: asyncio.StreamReader | None) -> str:
        if stream is None:
            return ""
        chunks: list[str] = []
        async for raw_line in stream:
            chunks.append(raw_line.decode("utf-8", errors="replace"))
        return "".join(chunks).strip()

    @staticmethod
    def _translate_event(payload: dict[str, Any]) -> WorkerProgressEvent:
        event_type = str(payload.get("type") or "event")
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}

        if event_type == "thread.started":
            thread_id = str(payload.get("thread_id") or "").strip()
            suffix = f" ({thread_id[:8]})" if thread_id else ""
            return WorkerProgressEvent(
                phase="worker_session",
                message=f"codex started a session{suffix}",
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "turn.started":
            return WorkerProgressEvent(
                phase="worker_step",
                message="codex started reasoning about the task",
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "item.completed":
            item_type = str(item.get("type") or "").strip()
            if item_type == "agent_message":
                text = str(item.get("text") or "").strip()
                preview = text[:200] if text else "codex produced a response"
                return WorkerProgressEvent(
                    phase="worker_text",
                    message=f"codex says: {preview}",
                    detail=text[:1200],
                    raw_type=event_type,
                    metadata=payload,
                )
            return WorkerProgressEvent(
                phase="worker_item",
                message=f"codex completed item: {item_type or 'item'}",
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "turn.completed":
            usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
            output_tokens = usage.get("output_tokens")
            detail = f"output_tokens={output_tokens}" if output_tokens is not None else ""
            return WorkerProgressEvent(
                phase="worker_step",
                message="codex finished the current turn",
                detail=detail,
                raw_type=event_type,
                metadata=payload,
            )

        return WorkerProgressEvent(
            phase="worker_event",
            message=f"codex event: {event_type}",
            raw_type=event_type,
            metadata=payload,
        )

    @staticmethod
    def _extract_final_message(raw_events: list[dict[str, Any]]) -> str:
        final_parts: list[str] = []
        for payload in raw_events:
            if str(payload.get("type") or "") != "item.completed":
                continue
            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
            if str(item.get("type") or "") != "agent_message":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                final_parts.append(text.strip())
        return "\n".join(final_parts).strip()

    @staticmethod
    def _extract_thread_id(raw_events: list[dict[str, Any]]) -> str:
        for payload in raw_events:
            if str(payload.get("type") or "") != "thread.started":
                continue
            thread_id = str(payload.get("thread_id") or "").strip()
            if thread_id:
                return thread_id
        return ""

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
        final_message: str,
        returncode: int,
    ) -> str:
        parts: list[str] = []
        if artifacts:
            created = [artifact.path for artifact in artifacts if artifact.change_type == "created"]
            modified = [artifact.path for artifact in artifacts if artifact.change_type == "modified"]
            if created:
                parts.append("Created: " + ", ".join(created[:5]))
            if modified:
                parts.append("Modified: " + ", ".join(modified[:5]))
        if final_message:
            parts.append(final_message[:240])
        if not parts:
            parts.append(f"codex finished with exit code {returncode}")
        return " | ".join(parts)
