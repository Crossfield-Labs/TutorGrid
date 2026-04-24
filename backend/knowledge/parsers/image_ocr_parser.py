from __future__ import annotations

import os
from pathlib import Path

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument


class ImageOcrParser:
    def __init__(self, *, lang: str | None = None, use_angle_cls: bool = True) -> None:
        self.lang = (lang or os.environ.get("ORCHESTRATOR_PADDLEOCR_LANG", "ch")).strip() or "ch"
        self.use_angle_cls = use_angle_cls
        self.engine = (os.environ.get("ORCHESTRATOR_OCR_ENGINE", "auto") or "auto").strip().lower()
        self.backend = "paddleocr"
        self._ocr_client = None

    def extract_lines(self, file_path: Path) -> list[str]:
        ocr = self._get_ocr_client()
        if self.backend == "rapidocr":
            return self._extract_lines_with_rapidocr(ocr, file_path)
        return self._extract_lines_with_paddleocr(ocr, file_path)

    def _extract_lines_with_paddleocr(self, ocr: object, file_path: Path) -> list[str]:
        raw = ocr.ocr(str(file_path), cls=self.use_angle_cls)
        lines: list[str] = []
        for page in raw or []:
            for item in page or []:
                if len(item) < 2:
                    continue
                text = str(item[1][0] if item[1] else "").strip()
                if text:
                    lines.append(text)
        return lines

    @staticmethod
    def _extract_lines_with_rapidocr(ocr: object, file_path: Path) -> list[str]:
        raw, _ = ocr(str(file_path))
        lines: list[str] = []
        for item in raw or []:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            text = str(item[1] or "").strip()
            if text:
                lines.append(text)
        return lines

    def parse(self, file_path: Path) -> ParsedDocument:
        lines = self.extract_lines(file_path)
        merged = "\n".join(lines).strip()
        blocks = [ParsedBlock(text=merged, section="ocr", page=1)] if merged else []
        return ParsedDocument(
            title=file_path.stem,
            blocks=blocks,
            metadata={
                "parser": self.backend,
                "sourcePath": str(file_path),
                "lang": self.lang,
            },
        )

    def _get_ocr_client(self):  # noqa: ANN001
        if self._ocr_client is None:
            self._ocr_client = self._build_ocr_client()
        return self._ocr_client

    def _build_ocr_client(self):  # noqa: ANN001
        order = self._engine_order()
        errors: dict[str, str] = {}
        for name in order:
            if name == "rapidocr":
                try:
                    from rapidocr_onnxruntime import RapidOCR

                    self.backend = "rapidocr"
                    return RapidOCR()
                except Exception as exc:  # pragma: no cover
                    errors["rapidocr"] = str(exc).strip() or "RapidOCR init failed."
                    continue
            try:
                from paddleocr import PaddleOCR

                client = PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.lang)
                self.backend = "paddleocr"
                return client
            except Exception as exc:  # pragma: no cover
                errors["paddleocr"] = str(exc).strip() or "PaddleOCR init failed."
                continue

        paddle_error = errors.get("paddleocr", "")
        rapid_error = errors.get("rapidocr", "")
        raise RuntimeError(
            "Image OCR engine is unavailable. "
            f"PaddleOCR error: {paddle_error[:300]}; RapidOCR error: {rapid_error[:300]}"
        )

    def _engine_order(self) -> list[str]:
        if self.engine in {"rapid", "rapidocr"}:
            return ["rapidocr", "paddleocr"]
        if self.engine in {"paddle", "paddleocr"}:
            return ["paddleocr", "rapidocr"]
        return ["paddleocr", "rapidocr"]
