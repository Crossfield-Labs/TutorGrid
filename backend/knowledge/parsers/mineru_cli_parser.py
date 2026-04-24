from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument


class MinerUCliParser:
    def __init__(
        self,
        *,
        binary: str | None = None,
        backend: str | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self.binary = (binary or os.environ.get("ORCHESTRATOR_MINERU_BINARY", "mineru")).strip() or "mineru"
        self.backend = (backend or os.environ.get("ORCHESTRATOR_MINERU_BACKEND", "pipeline")).strip()
        timeout_text = str(timeout_sec or os.environ.get("ORCHESTRATOR_MINERU_TIMEOUT_SEC", "900")).strip()
        try:
            self.timeout_sec = max(30, int(timeout_text))
        except ValueError:
            self.timeout_sec = 900

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def parse(self, file_path: Path) -> ParsedDocument:
        if not self.is_available():
            raise RuntimeError(f"MinerU CLI not found: {self.binary}")
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        with TemporaryDirectory(prefix="orchestrator_mineru_") as temp_dir:
            output_root = Path(temp_dir)
            command = [self.binary, "-p", str(file_path), "-o", str(output_root)]
            if self.backend:
                command.extend(["-b", self.backend])
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            if completed.returncode != 0:
                stderr_text = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(f"MinerU CLI failed: {stderr_text[:1200]}")
            markdown_path = self._pick_markdown_file(output_root=output_root, source_file=file_path)
            if markdown_path is None:
                raise RuntimeError("MinerU CLI did not generate markdown output.")
            markdown = markdown_path.read_text(encoding="utf-8", errors="replace").strip()
            if not markdown:
                raise RuntimeError("MinerU CLI markdown output is empty.")
            blocks = self._markdown_to_blocks(markdown)
            return ParsedDocument(
                title=file_path.stem,
                blocks=blocks,
                metadata={
                    "parser": "mineru-cli",
                    "sourcePath": str(file_path),
                    "backend": self.backend,
                    "markdownFile": str(markdown_path.name),
                },
            )

    @staticmethod
    def _pick_markdown_file(output_root: Path, source_file: Path) -> Path | None:
        candidates = [path for path in output_root.rglob("*.md") if path.is_file()]
        if not candidates:
            return None
        source_stem = source_file.stem.lower()
        preferred = [path for path in candidates if source_stem in path.stem.lower()]
        pool = preferred if preferred else candidates
        scored: list[tuple[int, Path]] = []
        for path in pool:
            try:
                size = len(path.read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                size = 0
            scored.append((size, path))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored else None

    @staticmethod
    def _markdown_to_blocks(markdown: str) -> list[ParsedBlock]:
        segments = [segment.strip() for segment in re.split(r"\n\s*\n", markdown) if segment.strip()]
        blocks: list[ParsedBlock] = []
        for index, segment in enumerate(segments, start=1):
            first_line = segment.splitlines()[0].strip()
            if first_line.startswith("#"):
                section = first_line.lstrip("#").strip() or f"section-{index}"
            else:
                section = f"section-{index}"
            blocks.append(
                ParsedBlock(
                    text=segment,
                    section=section,
                    page=0,
                    metadata={"segmentIndex": index, "format": "markdown"},
                )
            )
        return blocks
