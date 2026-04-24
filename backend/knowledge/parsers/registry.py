from __future__ import annotations

from pathlib import Path

from backend.knowledge.parsers.base import ParsedDocument, Parser
from backend.knowledge.parsers.doc_parser import DocParser
from backend.knowledge.parsers.docx_parser import DocxParser
from backend.knowledge.parsers.image_ocr_parser import ImageOcrParser
from backend.knowledge.parsers.pdf_parser import PdfParser
from backend.knowledge.parsers.plaintext_parser import PlainTextParser
from backend.knowledge.parsers.pptx_parser import PptxParser


class ParserRegistry:
    def __init__(self) -> None:
        self._fallback = PlainTextParser()
        self._mapping: dict[str, Parser] = {
            ".txt": self._fallback,
            ".md": self._fallback,
            ".pptx": PptxParser(),
            ".doc": DocParser(),
            ".docx": DocxParser(),
            ".pdf": PdfParser(),
            ".png": ImageOcrParser(),
            ".jpg": ImageOcrParser(),
            ".jpeg": ImageOcrParser(),
            ".bmp": ImageOcrParser(),
            ".webp": ImageOcrParser(),
        }

    def parse_document(self, file_path: Path) -> ParsedDocument:
        suffix = file_path.suffix.lower()
        parser = self._mapping.get(suffix, self._fallback)
        return parser.parse(file_path)
