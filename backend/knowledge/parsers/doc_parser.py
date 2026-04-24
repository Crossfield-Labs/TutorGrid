from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument
from backend.knowledge.parsers.docx_parser import DocxParser


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+")


class DocParser:
    """Parse legacy .doc files via available external backends.

    Backend order:
    1) antiword
    2) catdoc
    3) soffice/libreoffice (convert to txt)
    4) Microsoft Word COM automation on Windows
    """

    def __init__(self) -> None:
        self.antiword_binary = (os.environ.get("ORCHESTRATOR_DOC_ANTIWORD_BINARY", "antiword") or "antiword").strip()
        self.catdoc_binary = (os.environ.get("ORCHESTRATOR_DOC_CATDOC_BINARY", "catdoc") or "catdoc").strip()
        self.soffice_binary = (os.environ.get("ORCHESTRATOR_DOC_SOFFICE_BINARY", "soffice") or "soffice").strip()
        self.enable_word_com = self._bool_env("ORCHESTRATOR_DOC_WORD_COM_ENABLED", True)
        self.docx_parser = DocxParser()

    def parse(self, file_path: Path) -> ParsedDocument:
        binary = file_path.read_bytes()
        if binary.startswith(b"PK\x03\x04"):
            # Some uploads may use .doc suffix but contain DOCX payload.
            return self.docx_parser.parse(file_path)

        text = self._decode_plain_text(binary)
        if text:
            return self._build_document(file_path=file_path, text=text, parser_name="plaintext-doc")

        errors: list[str] = []
        extractors = [
            ("antiword", self._extract_with_antiword),
            ("catdoc", self._extract_with_catdoc),
            ("soffice", self._extract_with_soffice),
            ("word_com", self._extract_with_windows_word_com),
        ]
        for extractor_name, extractor in extractors:
            try:
                parsed_text, parser_name = extractor(file_path)
            except Exception as exc:
                errors.append(str(exc).strip() or f"{extractor_name} failed")
                continue
            if parsed_text:
                return self._build_document(file_path=file_path, text=parsed_text, parser_name=parser_name)
            errors.append(f"{extractor_name} returned empty text")

        error_message = " | ".join(item for item in errors if item)[:1200]
        raise RuntimeError(
            "DOC parsing failed. Install at least one backend (antiword/catdoc/soffice/Word COM). "
            f"Details: {error_message or 'no available parser backend'}"
        )

    def _extract_with_antiword(self, file_path: Path) -> tuple[str, str]:
        command = self._resolve_binary(self.antiword_binary)
        if not command:
            raise RuntimeError("antiword binary not found")
        completed = subprocess.run(
            [command, str(file_path)],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = self._decode_output(completed.stderr)
            raise RuntimeError(f"antiword failed: {stderr[:240]}")
        return self._sanitize_text(self._decode_output(completed.stdout)), "antiword"

    def _extract_with_catdoc(self, file_path: Path) -> tuple[str, str]:
        command = self._resolve_binary(self.catdoc_binary)
        if not command:
            raise RuntimeError("catdoc binary not found")
        completed = subprocess.run(
            [command, str(file_path)],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = self._decode_output(completed.stderr)
            raise RuntimeError(f"catdoc failed: {stderr[:240]}")
        return self._sanitize_text(self._decode_output(completed.stdout)), "catdoc"

    def _extract_with_soffice(self, file_path: Path) -> tuple[str, str]:
        command = self._resolve_binary(self.soffice_binary) or self._resolve_binary("libreoffice")
        if not command:
            raise RuntimeError("soffice/libreoffice binary not found")
        with TemporaryDirectory(prefix="orchestrator_doc_soffice_") as temp_dir:
            output_dir = Path(temp_dir)
            completed = subprocess.run(
                [
                    command,
                    "--headless",
                    "--convert-to",
                    "txt:Text",
                    "--outdir",
                    str(output_dir),
                    str(file_path),
                ],
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                stderr = self._decode_output(completed.stderr)
                raise RuntimeError(f"soffice conversion failed: {stderr[:240]}")
            candidates = list(output_dir.glob("*.txt"))
            if not candidates:
                raise RuntimeError("soffice conversion produced no txt file")
            raw = candidates[0].read_bytes()
            text = self._sanitize_text(self._decode_output(raw))
            return text, "soffice-txt"

    def _extract_with_windows_word_com(self, file_path: Path) -> tuple[str, str]:
        if os.name != "nt":
            raise RuntimeError("Word COM parser is only available on Windows")
        if not self.enable_word_com:
            raise RuntimeError("Word COM parser is disabled by ORCHESTRATOR_DOC_WORD_COM_ENABLED")
        powershell = self._resolve_binary("powershell") or self._resolve_binary("pwsh")
        if not powershell:
            raise RuntimeError("PowerShell runtime not found")
        with TemporaryDirectory(prefix="orchestrator_doc_wordcom_") as temp_dir:
            output_path = Path(temp_dir) / "converted.txt"
            input_literal = self._ps_literal(str(file_path.resolve()))
            output_literal = self._ps_literal(str(output_path.resolve()))
            script = (
                "$ErrorActionPreference='Stop';"
                f"$in={input_literal};"
                f"$out={output_literal};"
                "$word=New-Object -ComObject Word.Application;"
                "$word.Visible=$false;"
                "$word.DisplayAlerts=0;"
                "$doc=$word.Documents.Open($in,$false,$true);"
                "$wdFormatUnicodeText=7;"
                "$doc.SaveAs([ref]$out,[ref]$wdFormatUnicodeText);"
                "$doc.Close();"
                "$word.Quit();"
            )
            completed = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                stderr = self._decode_output(completed.stderr)
                raise RuntimeError(f"Word COM conversion failed: {stderr[:240]}")
            if not output_path.exists():
                raise RuntimeError("Word COM conversion produced no output")
            text = ""
            try:
                text = self._sanitize_text(output_path.read_text(encoding="utf-16", errors="replace"))
            except Exception:
                text = ""
            if not text:
                text = self._sanitize_text(output_path.read_text(encoding="utf-8", errors="replace"))
            return text, "word-com"

    def _decode_plain_text(self, binary: bytes) -> str:
        # Avoid treating OLE2 containers as plain text.
        if binary.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return ""
        text = self._decode_output(binary)
        return self._sanitize_text(text)

    @staticmethod
    def _resolve_binary(name: str) -> str:
        candidate = str(name or "").strip()
        if not candidate:
            return ""
        path = shutil.which(candidate)
        return path or ""

    @staticmethod
    def _decode_output(raw: bytes) -> str:
        if not raw:
            return ""
        for encoding in ("utf-8", "utf-16", "gb18030", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except Exception:
                continue
        # Last resort keeps pipeline alive for noisy outputs.
        return raw.decode("utf-8", errors="replace")

    @classmethod
    def _sanitize_text(cls, text: str) -> str:
        normalized = str(text or "").replace("\x00", "").strip()
        if not normalized:
            return ""
        printable = sum(1 for ch in normalized if ch.isprintable() or ch in "\n\r\t")
        ratio = printable / max(1, len(normalized))
        if ratio < 0.85:
            return ""
        token_count = len(_TOKEN_PATTERN.findall(normalized))
        if token_count < 3:
            return ""
        return normalized

    @staticmethod
    def _build_document(*, file_path: Path, text: str, parser_name: str) -> ParsedDocument:
        lines = [item.strip() for item in text.splitlines() if item.strip()]
        blocks: list[ParsedBlock] = []
        if lines:
            for index, line in enumerate(lines, start=1):
                blocks.append(
                    ParsedBlock(
                        text=line,
                        section=f"paragraph-{index}",
                        page=0,
                        metadata={"paragraphIndex": index},
                    )
                )
        else:
            blocks.append(ParsedBlock(text=text.strip(), section="paragraph-1", page=0, metadata={"paragraphIndex": 1}))
        return ParsedDocument(
            title=file_path.stem,
            blocks=blocks,
            metadata={"parser": parser_name, "sourcePath": str(file_path)},
        )

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", ""}

    @staticmethod
    def _ps_literal(path_text: str) -> str:
        escaped = path_text.replace("'", "''")
        return f"'{escaped}'"
