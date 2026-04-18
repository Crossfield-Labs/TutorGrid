from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Awaitable, Callable

from orchestrator.workers.models import WorkerArtifact, WorkerProgressEvent, WorkerResult

WorkerProgressCallback = Callable[[WorkerProgressEvent], Awaitable[None]]


def resolve_command(configured: str) -> str:
    candidate = (configured or "").strip()
    if not candidate:
        raise RuntimeError("Worker command is not configured.")

    configured_path = Path(candidate)
    if configured_path.exists():
        return str(configured_path)

    for item in (candidate, f"{candidate}.cmd", f"{candidate}.bat", f"{candidate}.exe"):
        resolved = shutil.which(item)
        if resolved:
            return resolved
    raise FileNotFoundError(f"Unable to locate worker command: {candidate}")


def snapshot_workspace(workspace: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    if not workspace.exists():
        return snapshot
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        snapshot[str(path.relative_to(workspace)).replace("\\", "/")] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def diff_workspace(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[WorkerArtifact]:
    artifacts: list[WorkerArtifact] = []
    for path, (_, size) in after.items():
        if path not in before:
            artifacts.append(WorkerArtifact(path=path, change_type="created", size=size))
        elif before[path] != after[path]:
            artifacts.append(WorkerArtifact(path=path, change_type="modified", size=size))
    return sorted(artifacts, key=lambda item: (item.change_type, item.path))


async def _consume_stream(
    stream: asyncio.StreamReader | None,
    *,
    phase: str,
    worker_name: str,
    on_progress: WorkerProgressCallback | None = None,
) -> str:
    if stream is None:
        return ""

    chunks: list[str] = []
    async for raw_line in stream:
        line = raw_line.decode("utf-8", errors="replace").rstrip()
        if not line:
            continue
        chunks.append(line)
        if on_progress is not None:
            await on_progress(
                WorkerProgressEvent(
                    phase=phase,
                    message=f"{worker_name} {phase}: {line[:280]}",
                    detail=line[:1200],
                    raw_type=phase,
                    metadata={"worker": worker_name},
                )
            )
    return "\n".join(chunks).strip()


async def run_cli_worker(
    *,
    worker_name: str,
    command: list[str],
    workspace: str,
    task: str,
    on_progress: WorkerProgressCallback | None = None,
) -> WorkerResult:
    workspace_path = Path(workspace or ".").resolve()
    before = snapshot_workspace(workspace_path)
    if on_progress is not None:
        await on_progress(
            WorkerProgressEvent(
                phase="worker_session",
                message=f"{worker_name} started.",
                raw_type="worker_session",
                metadata={"worker": worker_name},
            )
        )

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(workspace_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_task = asyncio.create_task(
        _consume_stream(process.stdout, phase="worker_output", worker_name=worker_name, on_progress=on_progress)
    )
    stderr_task = asyncio.create_task(
        _consume_stream(process.stderr, phase="worker_error", worker_name=worker_name, on_progress=on_progress)
    )
    output, error_text = await asyncio.gather(stdout_task, stderr_task)
    returncode = await process.wait()
    after = snapshot_workspace(workspace_path)
    artifacts = diff_workspace(before, after)

    success = returncode == 0
    summary_source = output or error_text or f"{worker_name} exited with code {returncode}"
    summary = summary_source[:240]
    if on_progress is not None:
        final_message = f"{worker_name} completed." if success else f"{worker_name} failed."
        await on_progress(
            WorkerProgressEvent(
                phase="worker_progress",
                message=final_message,
                raw_type="worker_progress",
                metadata={"worker": worker_name, "returncode": returncode},
            )
        )

    return WorkerResult(
        worker=worker_name,
        success=success,
        summary=summary,
        output=output or summary_source,
        artifacts=artifacts,
        error="" if success else (error_text or summary_source),
        metadata={"task": task, "returncode": returncode, "command": list(command), "workspace": str(workspace_path)},
    )
