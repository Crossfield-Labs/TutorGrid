from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument
from backend.knowledge.parsers.image_ocr_parser import ImageOcrParser
from backend.knowledge.parsers.mineru_cli_parser import MinerUCliParser


class PdfParser:
    def __init__(self) -> None:
        self.strategy = os.environ.get("ORCHESTRATOR_PDF_PARSE_STRATEGY", "auto").strip().lower() or "auto"
        self.enable_mineru = self._bool_env("ORCHESTRATOR_MINERU_ENABLED", True)
        self.enable_ocr_fallback = self._bool_env("ORCHESTRATOR_PDF_OCR_FALLBACK", True)
        dpi_text = os.environ.get("ORCHESTRATOR_PDF_OCR_DPI", "220").strip()
        try:
            self.ocr_dpi = max(96, int(dpi_text))
        except ValueError:
            self.ocr_dpi = 220
        self.mineru_parser = MinerUCliParser()
        self.ocr_parser = ImageOcrParser()

    def parse(self, file_path: Path) -> ParsedDocument:
        normalized_strategy = self.strategy if self.strategy in {"auto", "mineru", "pymupdf", "ocr"} else "auto"
        mineru_error = ""
        if normalized_strategy in {"auto", "mineru"} and self.enable_mineru:
            try:
                parsed = self.mineru_parser.parse(file_path)
                if parsed.blocks:
                    return parsed
                mineru_error = "MinerU parser returned empty blocks."
            except Exception as exc:
                mineru_error = str(exc).strip() or "MinerU parser failed."
            if normalized_strategy == "mineru":
                raise RuntimeError(mineru_error)

        text_blocks: list[ParsedBlock] = []
        if normalized_strategy in {"auto", "pymupdf", "ocr"}:
            text_blocks = self._parse_with_pymupdf_text(file_path)
            if text_blocks and normalized_strategy != "ocr":
                return ParsedDocument(
                    title=file_path.stem,
                    blocks=text_blocks,
                    metadata={"parser": "pymupdf", "sourcePath": str(file_path)},
                )

        if normalized_strategy in {"auto", "pymupdf"}:
            text_blocks = self._parse_with_pdfplumber_text(file_path)
            if text_blocks:
                return ParsedDocument(
                    title=file_path.stem,
                    blocks=text_blocks,
                    metadata={"parser": "pdfplumber", "sourcePath": str(file_path)},
                )

        sidecar_blocks = self._parse_with_sidecar_text(file_path)
        if sidecar_blocks:
            return ParsedDocument(
                title=file_path.stem,
                blocks=sidecar_blocks,
                metadata={"parser": "pdf-sidecar", "sourcePath": str(file_path)},
            )

        if normalized_strategy in {"auto", "ocr"} and self.enable_ocr_fallback:
            ocr_blocks = self._parse_with_ocr(file_path)
            if ocr_blocks:
                return ParsedDocument(
                    title=file_path.stem,
                    blocks=ocr_blocks,
                    metadata={"parser": "pymupdf+paddleocr", "sourcePath": str(file_path)},
                )

        if text_blocks:
            return ParsedDocument(
                title=file_path.stem,
                blocks=text_blocks,
                metadata={"parser": "pdf-text", "sourcePath": str(file_path)},
            )

        if mineru_error:
            raise RuntimeError(f"PDF parsing failed. MinerU error: {mineru_error}")
        raise RuntimeError("PDF parsing failed: no text extracted and OCR fallback produced no result.")

    def _parse_with_pymupdf_text(self, file_path: Path) -> list[ParsedBlock]:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover
            if self.strategy == "pymupdf":
                raise RuntimeError("PyMuPDF is required for PDF parsing.") from exc
            return []

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            if self.strategy == "pymupdf":
                raise RuntimeError("PyMuPDF failed to read PDF text.") from exc
            return []
        blocks: list[ParsedBlock] = []
        try:
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                text = str(page.get_text("text") or "").strip()
                if not text:
                    continue
                blocks.append(
                    ParsedBlock(
                        text=text,
                        section=f"page-{page_index + 1}",
                        page=page_index + 1,
                        metadata={"pageIndex": page_index + 1, "source": "text"},
                    )
                )
        finally:
            doc.close()
        return blocks

    def _parse_with_pdfplumber_text(self, file_path: Path) -> list[ParsedBlock]:
        try:
            import pdfplumber
        except ImportError:
            return []

        blocks: list[ParsedBlock] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    text = str(page.extract_text() or "").strip()
                    if not text:
                        continue
                    blocks.append(
                        ParsedBlock(
                            text=text,
                            section=f"page-{page_index}",
                            page=page_index,
                            metadata={"pageIndex": page_index, "source": "pdfplumber"},
                        )
                    )
        except Exception:
            return []
        return blocks

    def _parse_with_sidecar_text(self, file_path: Path) -> list[ParsedBlock]:
        sidecar = self._find_sidecar_text(file_path)
        if sidecar is None:
            return []
        text = sidecar.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return []

        import re

        marker = re.compile(
            r"^\s*(?:---\s*)?(?:(?:page|p)\s*(\d+)|\u7b2c\s*(\d+)\s*\u9875)\s*(?:---)?\s*$",
            re.IGNORECASE,
        )
        blocks: list[ParsedBlock] = []
        current_page = 0
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_lines
            merged = "\n".join(line for line in current_lines if line.strip()).strip()
            if not merged:
                current_lines = []
                return
            blocks.append(
                ParsedBlock(
                    text=merged,
                    section=f"page-{current_page}" if current_page else sidecar.stem,
                    page=current_page,
                    metadata={
                        "pageIndex": current_page,
                        "source": "sidecar",
                        "sidecarPath": str(sidecar),
                    },
                )
            )
            current_lines = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            match = marker.match(line)
            if match:
                flush()
                page_text = next(group for group in match.groups() if group)
                current_page = int(page_text)
                continue
            current_lines.append(raw_line)
        flush()
        if blocks:
            return blocks
        return [
            ParsedBlock(
                text=text,
                section=sidecar.stem,
                page=0,
                metadata={"pageIndex": 0, "source": "sidecar", "sidecarPath": str(sidecar)},
            )
        ]

    @staticmethod
    def _find_sidecar_text(file_path: Path) -> Path | None:
        candidates = [
            file_path.with_name(f"{file_path.name}.ocr.txt"),
            file_path.with_name(f"{file_path.stem}.ocr.txt"),
            file_path.with_name(f"{file_path.stem}.txt"),
            file_path.with_name(f"{file_path.stem}.md"),
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _parse_with_ocr(self, file_path: Path) -> list[ParsedBlock]:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PyMuPDF is required for OCR fallback on PDFs.") from exc

        doc = fitz.open(str(file_path))
        blocks: list[ParsedBlock] = []
        try:
            with TemporaryDirectory(prefix="orchestrator_pdf_ocr_") as temp_dir:
                temp_root = Path(temp_dir)
                for page_index in range(doc.page_count):
                    page = doc.load_page(page_index)
                    pixmap = page.get_pixmap(dpi=self.ocr_dpi, alpha=False)
                    page_image = temp_root / f"page_{page_index + 1}.png"
                    pixmap.save(str(page_image))
                    lines = self.ocr_parser.extract_lines(page_image)
                    text = "\n".join(lines).strip()
                    if not text:
                        continue
                    blocks.append(
                        ParsedBlock(
                            text=text,
                            section=f"page-{page_index + 1}",
                            page=page_index + 1,
                            metadata={"pageIndex": page_index + 1, "source": "ocr"},
                        )
                    )
        finally:
            doc.close()
        return blocks

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", ""}
