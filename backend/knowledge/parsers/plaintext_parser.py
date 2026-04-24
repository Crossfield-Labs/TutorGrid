from __future__ import annotations

from pathlib import Path

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument


class PlainTextParser:
    def parse(self, file_path: Path) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = [item.strip() for item in text.splitlines()]
        blocks = [ParsedBlock(text=line, section="", page=0) for line in lines if line]
        if not blocks and text.strip():
            blocks = [ParsedBlock(text=text.strip(), section="", page=0)]
        return ParsedDocument(
            title=file_path.stem,
            blocks=blocks,
            metadata={"parser": "plaintext", "sourcePath": str(file_path)},
        )

