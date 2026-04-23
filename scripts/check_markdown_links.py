from __future__ import annotations

import re
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _iter_markdown_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and "node_modules" not in path.parts and "__pycache__" not in path.parts
    ]


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def _normalize_target(path: Path, target: str) -> Path | None:
    clean_target = target.split("#", 1)[0].strip()
    if not clean_target or _is_external(clean_target):
        return None
    return (path.parent / clean_target).resolve()


def main() -> int:
    failures: list[str] = []
    for markdown_file in _iter_markdown_files():
        text = markdown_file.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            resolved = _normalize_target(markdown_file, target)
            if resolved is None:
                continue
            if not resolved.exists():
                failures.append(f"{markdown_file.relative_to(ROOT)} -> {target}")

    if failures:
        print("Broken markdown links found:")
        for item in failures:
            print(item)
        return 1

    print("Markdown links OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
