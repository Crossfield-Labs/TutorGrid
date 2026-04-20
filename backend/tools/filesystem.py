from __future__ import annotations

from pathlib import Path
from typing import Any


async def list_files(path: str = ".") -> str:
    target = Path(path).resolve()
    if not target.exists():
        return f"Error: Path does not exist: {target}"
    return "\n".join(
        f"- {'DIR' if item.is_dir() else 'FILE'} {item.name}"
        for item in sorted(target.iterdir(), key=lambda value: (value.is_file(), value.name.lower()))
    )


async def read_file(path: str) -> str:
    target = Path(path).resolve()
    if not target.exists() or not target.is_file():
        return f"Error: File does not exist: {target}"
    return target.read_text(encoding="utf-8", errors="replace")[:12000]

