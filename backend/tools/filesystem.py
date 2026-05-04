from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_MAX_READ_BYTES = 12000
_MAX_WRITE_BYTES = 200_000
_MAX_GLOB_RESULTS = 200
_MAX_GREP_MATCHES = 100
_GREP_FILE_LIMIT = 400


def _resolve_against_workspace(path: str, workspace: str | None) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() and workspace:
        candidate = Path(workspace) / path
    return candidate.resolve()


async def list_files(path: str = ".", *, workspace: str | None = None) -> str:
    target = _resolve_against_workspace(path, workspace) if workspace else Path(path).resolve()
    if not target.exists():
        return f"Error: Path does not exist: {target}"
    if target.is_file():
        return f"- FILE {target.name}"
    return "\n".join(
        f"- {'DIR' if item.is_dir() else 'FILE'} {item.name}"
        for item in sorted(target.iterdir(), key=lambda value: (value.is_file(), value.name.lower()))
    )


async def read_file(path: str, *, workspace: str | None = None) -> str:
    target = _resolve_against_workspace(path, workspace) if workspace else Path(path).resolve()
    if not target.exists() or not target.is_file():
        return f"Error: File does not exist: {target}"
    return target.read_text(encoding="utf-8", errors="replace")[:_MAX_READ_BYTES]


async def write_file(path: str, content: str, *, workspace: str | None = None) -> str:
    if content is None:
        return "Error: write_file requires non-null content."
    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) > _MAX_WRITE_BYTES:
        return f"Error: content exceeds {_MAX_WRITE_BYTES} bytes; chunk the write or use a worker."
    target = _resolve_against_workspace(path, workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    target.write_text(content, encoding="utf-8")
    verb = "Updated" if existed else "Created"
    return f"{verb} {target} ({len(encoded)} bytes)."


async def edit_file(
    path: str,
    old: str,
    new: str,
    *,
    workspace: str | None = None,
    occurrences: int = 1,
) -> str:
    if not old:
        return "Error: edit_file requires a non-empty 'old' string."
    target = _resolve_against_workspace(path, workspace)
    if not target.exists() or not target.is_file():
        return f"Error: File does not exist: {target}"
    text = target.read_text(encoding="utf-8", errors="replace")
    count = text.count(old)
    if count == 0:
        return f"Error: 'old' string not found in {target}."
    if occurrences > 0 and count > occurrences and old != new:
        return (
            f"Error: 'old' string appears {count} times in {target}, but occurrences={occurrences}."
            " Provide more surrounding context or set occurrences=0 to replace all."
        )
    replace_count = -1 if occurrences == 0 else max(1, occurrences)
    updated = text.replace(old, new, replace_count) if replace_count != -1 else text.replace(old, new)
    if updated == text:
        return f"Error: replacement produced no change in {target}."
    target.write_text(updated, encoding="utf-8")
    actual = count if replace_count == -1 else min(replace_count, count)
    return f"Edited {target} ({actual} replacement(s))."


async def glob_files(pattern: str, *, workspace: str | None = None) -> str:
    if not pattern:
        return "Error: glob requires a pattern."
    root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    if not root.exists():
        return f"Error: workspace does not exist: {root}"
    matches: list[str] = []
    for hit in root.glob(pattern):
        if hit.is_file():
            try:
                matches.append(str(hit.relative_to(root)).replace("\\", "/"))
            except ValueError:
                matches.append(str(hit))
        if len(matches) >= _MAX_GLOB_RESULTS:
            break
    if not matches:
        return f"No files matched pattern '{pattern}' under {root}."
    body = "\n".join(f"- {item}" for item in matches)
    truncated = " (truncated)" if len(matches) >= _MAX_GLOB_RESULTS else ""
    return f"Matched {len(matches)} file(s){truncated}:\n{body}"


async def grep_files(
    pattern: str,
    *,
    path: str = ".",
    workspace: str | None = None,
    include: str = "",
    case_insensitive: bool = False,
) -> str:
    if not pattern:
        return "Error: grep requires a non-empty pattern."
    base = _resolve_against_workspace(path, workspace) if path else Path(workspace or ".").resolve()
    if not base.exists():
        return f"Error: path does not exist: {base}"
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as error:
        return f"Error: invalid regex '{pattern}': {error}"
    files: list[Path] = []
    if base.is_file():
        files.append(base)
    else:
        glob_pattern = include if include else "**/*"
        for hit in base.glob(glob_pattern):
            if hit.is_file():
                files.append(hit)
            if len(files) >= _GREP_FILE_LIMIT:
                break
    matches: list[str] = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                rel = (
                    str(file_path.relative_to(base if base.is_dir() else base.parent)).replace("\\", "/")
                    if base.is_dir() or base.parent
                    else str(file_path)
                )
                matches.append(f"{rel}:{line_no}: {line[:240]}")
                if len(matches) >= _MAX_GREP_MATCHES:
                    break
        if len(matches) >= _MAX_GREP_MATCHES:
            break
    if not matches:
        return f"No matches for /{pattern}/ under {base}."
    truncated = " (truncated)" if len(matches) >= _MAX_GREP_MATCHES else ""
    return f"Found {len(matches)} match(es){truncated}:\n" + "\n".join(matches)

