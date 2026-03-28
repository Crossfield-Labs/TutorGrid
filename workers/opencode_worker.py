from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from config.subagent_config import SubAgentConfig
from workers.base import WorkerAdapter, WorkerProgressCallback
from workers.models import WorkerArtifact, WorkerProgressEvent, WorkerResult


class OpencodeWorker(WorkerAdapter):
    def __init__(self, config: SubAgentConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def description(self) -> str:
        return "Delegate a focused coding or analysis task to the local opencode CLI."

    async def run(
        self,
        *,
        task: str,
        workspace: str,
        on_progress: WorkerProgressCallback | None = None,
    ) -> WorkerResult:
        workspace_path = Path(workspace or ".").resolve()
        before = self._snapshot_workspace(workspace_path)
        command = self._build_command(task, workspace_path)

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
        final_message = self._extract_final_message(stdout_lines)
        summary = self._build_summary(artifacts, final_message, returncode)
        if returncode != 0:
            error_text = stderr or final_message or f"opencode exited with code {returncode}"
            return WorkerResult(
                worker=self.name,
                success=False,
                summary=summary,
                output=final_message,
                artifacts=artifacts,
                raw_events=raw_events,
                error=error_text,
            )

        return WorkerResult(
            worker=self.name,
            success=True,
            summary=summary,
            output=final_message or "\n".join(stdout_lines[-20:]),
            artifacts=artifacts,
            raw_events=raw_events,
        )

    def _build_command(self, task: str, workspace: Path) -> list[str]:
        executable = self._resolve_command()
        command = [
            executable,
            "run",
            "--format",
            "json",
            "--dir",
            str(workspace),
        ]
        if self.config.opencode_model:
            command.extend(["--model", self.config.opencode_model])
        if self.config.opencode_agent:
            command.extend(["--agent", self.config.opencode_agent])
        command.append(task)
        return command

    def _resolve_command(self) -> str:
        configured = self.config.opencode_command.strip()
        if not configured:
            raise RuntimeError("opencode command is not configured.")

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
        raise FileNotFoundError(f"Unable to locate opencode command: {configured}")

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
            parsed = self._parse_event(line)
            if parsed is not None:
                raw_events.append(parsed)
                if on_progress:
                    await on_progress(self._translate_event(parsed))
            elif on_progress:
                await on_progress(
                    WorkerProgressEvent(
                        phase="worker_output",
                        message=f"opencode output: {line[:200]}",
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
    def _parse_event(line: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _translate_event(payload: dict[str, Any]) -> WorkerProgressEvent:
        event_type = str(payload.get("type") or payload.get("event") or "event")
        part = payload.get("part") if isinstance(payload.get("part"), dict) else {}

        if event_type == "tool_use":
            tool_name = str(
                part.get("name")
                or part.get("tool")
                or part.get("toolName")
                or payload.get("name")
                or "internal tool"
            )
            target = str(
                part.get("path")
                or part.get("file")
                or part.get("command")
                or part.get("input")
                or ""
            ).strip()
            suffix = f" -> {target[:120]}" if target else ""
            return WorkerProgressEvent(
                phase="worker_tool",
                message=f"opencode is using {tool_name}{suffix}",
                detail=target[:300],
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "text":
            text = str(part.get("text") or payload.get("text") or payload.get("content") or "").strip()
            preview = text[:200] if text else "opencode produced a text update"
            return WorkerProgressEvent(
                phase="worker_text",
                message=f"opencode says: {preview}",
                detail=text[:1000],
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "step_start":
            return WorkerProgressEvent(
                phase="worker_step",
                message="opencode started a work step",
                raw_type=event_type,
                metadata=payload,
            )

        if event_type == "step_finish":
            reason = str(part.get("reason") or payload.get("reason") or "step finished")
            return WorkerProgressEvent(
                phase="worker_step",
                message=f"opencode finished a work step ({reason})",
                detail=reason,
                raw_type=event_type,
                metadata=payload,
            )

        return WorkerProgressEvent(
            phase="worker_event",
            message=f"opencode event: {event_type}",
            raw_type=event_type,
            metadata=payload,
        )

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
    def _extract_final_message(lines: list[str]) -> str:
        final_parts: list[str] = []
        for line in lines:
            payload = OpencodeWorker._parse_event(line)
            if payload is None:
                continue
            event_type = str(payload.get("type") or payload.get("event") or "")
            part = payload.get("part") if isinstance(payload.get("part"), dict) else {}
            if event_type in {"text", "message", "assistant", "response.completed"}:
                text = part.get("text") or payload.get("text") or payload.get("content") or payload.get("message")
                if isinstance(text, str) and text.strip():
                    final_parts.append(text.strip())
        return "\n".join(final_parts).strip()

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
            parts.append(f"opencode finished with exit code {returncode}")
        return " | ".join(parts)
