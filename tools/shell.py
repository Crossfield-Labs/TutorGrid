from __future__ import annotations

import asyncio
import locale
import shutil


async def run_shell(command: str, timeout_seconds: int = 90) -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    process = await asyncio.create_subprocess_exec(
        executable,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return f"Error: Command timed out after {timeout_seconds} seconds"
    return _decode(stdout, stderr)


def _decode(stdout: bytes, stderr: bytes) -> str:
    chunks: list[str] = []
    for raw in (stdout, stderr):
        if not raw:
            continue
        for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk", "cp936"):
            try:
                chunks.append(raw.decode(encoding))
                break
            except (LookupError, UnicodeDecodeError):
                continue
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
