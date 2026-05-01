from __future__ import annotations

import sys
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.knowledge.parsers.base import ParsedBlock, ParsedDocument
from backend.knowledge.parsers.doc_parser import DocParser
from backend.knowledge.parsers.docx_parser import DocxParser
from backend.knowledge.parsers.image_ocr_parser import ImageOcrParser
from backend.knowledge.parsers.mineru_cli_parser import MinerUCliParser
from backend.knowledge.parsers.pdf_parser import PdfParser
from backend.knowledge.parsers.pptx_parser import PptxParser


class _FakeOcrClient:
    def __init__(self) -> None:
        self.calls = 0

    def ocr(self, file_path: str, cls: bool = True):  # noqa: ANN001
        _ = file_path
        _ = cls
        self.calls += 1
        return [[[None, ("line one", 0.99)], [None, ("line two", 0.95)]]]


class _FakeLineOcrParser:
    def __init__(self, lines: list[str]) -> None:
        self.lines = list(lines)

    def extract_lines(self, file_path: Path) -> list[str]:
        _ = file_path
        return list(self.lines)


class KnowledgeParsersTests(unittest.TestCase):
    def test_mineru_cli_parser_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "paper.pdf"
            source_path.write_bytes(b"%PDF-1.4 fake")
            parser = MinerUCliParser(binary="mineru", backend="pipeline", timeout_sec=60)

            def _fake_run(command: list[str], **kwargs):  # noqa: ANN001
                _ = kwargs
                output_root = Path(command[command.index("-o") + 1])
                md_path = output_root / "result" / "paper_output.md"
                md_path.parent.mkdir(parents=True, exist_ok=True)
                md_path.write_text("# Intro\n\nThis is a parsed markdown body.", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                patch("backend.knowledge.parsers.mineru_cli_parser.shutil.which", return_value="mineru"),
                patch("backend.knowledge.parsers.mineru_cli_parser.subprocess.run", side_effect=_fake_run),
            ):
                parsed = parser.parse(source_path)
            self.assertEqual(parsed.metadata.get("parser"), "mineru-cli")
            self.assertGreaterEqual(len(parsed.blocks), 2)
            self.assertIn("parsed markdown", parsed.blocks[-1].text)

    def test_mineru_cli_parser_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "paper.pdf"
            source_path.write_bytes(b"%PDF-1.4 fake")
            parser = MinerUCliParser(binary="mineru")
            with patch("backend.knowledge.parsers.mineru_cli_parser.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError):
                    parser.parse(source_path)

    def test_image_ocr_parser_reuses_client(self) -> None:
        parser = ImageOcrParser(lang="en")
        fake_client = _FakeOcrClient()
        with patch.object(parser, "_build_ocr_client", return_value=fake_client) as build_mock:
            with tempfile.TemporaryDirectory() as temp_dir:
                image_path = Path(temp_dir) / "sample.png"
                image_path.write_bytes(b"fake-image")
                first_lines = parser.extract_lines(image_path)
                second_lines = parser.extract_lines(image_path)
        self.assertEqual(first_lines, ["line one", "line two"])
        self.assertEqual(second_lines, ["line one", "line two"])
        self.assertEqual(fake_client.calls, 2)
        self.assertEqual(build_mock.call_count, 1)

    def test_pptx_parser_extracts_text_and_image_ocr(self) -> None:
        class _FakeImage:
            def __init__(self, blob: bytes, ext: str) -> None:
                self.blob = blob
                self.ext = ext

        class _FakeTextShape:
            has_text_frame = True
            text = "Slide title"

        class _FakeImageShape:
            has_text_frame = False
            image = _FakeImage(blob=b"fake-image", ext="png")

        class _FakeSlide:
            def __init__(self) -> None:
                self.shapes = [_FakeTextShape(), _FakeImageShape()]

        class _FakePresentation:
            def __init__(self, path: str) -> None:  # noqa: ARG002
                self.slides = [_FakeSlide()]

        fake_pptx_module = types.SimpleNamespace(Presentation=_FakePresentation)
        with (
            patch.dict(sys.modules, {"pptx": fake_pptx_module}),
            patch(
                "backend.knowledge.parsers.pptx_parser.ImageOcrParser",
                return_value=_FakeLineOcrParser(["diagram label", "formula note"]),
            ),
        ):
            parser = PptxParser()
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = Path(temp_dir) / "deck.pptx"
                file_path.write_bytes(b"fake-pptx")
                parsed = parser.parse(file_path)

        self.assertEqual(parsed.metadata.get("parser"), "python-pptx")
        self.assertTrue(any(block.text == "Slide title" for block in parsed.blocks))
        image_blocks = [block for block in parsed.blocks if block.metadata.get("source") == "image_ocr"]
        self.assertEqual(len(image_blocks), 1)
        self.assertIn("diagram label", image_blocks[0].text)

    def test_docx_parser_extracts_text_and_image_ocr(self) -> None:
        class _FakeParagraph:
            def __init__(self, text: str) -> None:
                self.text = text

        class _FakeImagePart:
            def __init__(self, partname: str, blob: bytes) -> None:
                self.partname = partname
                self.blob = blob

        class _FakeRelationship:
            def __init__(self, target_part: object) -> None:
                self.target_part = target_part

        class _FakePart:
            def __init__(self) -> None:
                self.rels = {
                    "rId1": _FakeRelationship(_FakeImagePart("/word/media/image1.png", b"img-a")),
                    "rId2": _FakeRelationship(_FakeImagePart("/word/media/image2.jpg", b"img-b")),
                }

        class _FakeDocument:
            def __init__(self, path: str) -> None:  # noqa: ARG002
                self.paragraphs = [_FakeParagraph("Paragraph one"), _FakeParagraph("Paragraph two")]
                self.part = _FakePart()

        fake_docx_module = types.SimpleNamespace(Document=_FakeDocument)
        with (
            patch.dict(sys.modules, {"docx": fake_docx_module}),
            patch(
                "backend.knowledge.parsers.docx_parser.ImageOcrParser",
                return_value=_FakeLineOcrParser(["embedded chart text"]),
            ),
        ):
            parser = DocxParser()
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = Path(temp_dir) / "notes.docx"
                file_path.write_bytes(b"fake-docx")
                parsed = parser.parse(file_path)

        self.assertEqual(parsed.metadata.get("parser"), "python-docx")
        paragraph_blocks = [block for block in parsed.blocks if block.section.startswith("paragraph-")]
        self.assertEqual(len(paragraph_blocks), 2)
        image_blocks = [block for block in parsed.blocks if block.metadata.get("source") == "image_ocr"]
        self.assertEqual(len(image_blocks), 2)
        self.assertTrue(all("embedded chart text" in block.text for block in image_blocks))

    def test_doc_parser_extracts_text_with_antiword(self) -> None:
        parser = DocParser()
        fake_stdout = "Observer pattern defines one-to-many dependency.\nUse subject/observer interfaces."
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "legacy.doc"
            file_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00")
            with (
                patch("backend.knowledge.parsers.doc_parser.shutil.which", return_value="antiword"),
                patch(
                    "backend.knowledge.parsers.doc_parser.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        args=["antiword", str(file_path)],
                        returncode=0,
                        stdout=fake_stdout.encode("utf-8"),
                        stderr=b"",
                    ),
                ),
            ):
                parsed = parser.parse(file_path)

        self.assertEqual(parsed.metadata.get("parser"), "antiword")
        self.assertTrue(parsed.blocks)
        self.assertIn("Observer pattern defines one-to-many dependency.", parsed.blocks[0].text)

    def test_doc_parser_decodes_gbk_output(self) -> None:
        sample = "测试使用Doc文档"
        encoded = sample.encode("gb18030")
        decoded = DocParser._decode_output(encoded)
        self.assertEqual(decoded, sample)

    def test_doc_parser_raises_when_no_backend_available(self) -> None:
        parser = DocParser()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "legacy.doc"
            file_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00")
            with (
                patch("backend.knowledge.parsers.doc_parser.shutil.which", return_value=None),
                patch("backend.knowledge.parsers.doc_parser.DocParser._extract_with_windows_word_com", return_value=("", "word-com")),
            ):
                with self.assertRaises(RuntimeError):
                    parser.parse(file_path)

    def test_pdf_parser_prefers_mineru_in_auto_mode(self) -> None:
        parser = PdfParser()
        parser.strategy = "auto"
        parser.enable_mineru = True
        mineru_doc = ParsedDocument(
            title="paper",
            blocks=[ParsedBlock(text="mineru block", section="intro", page=1)],
            metadata={"parser": "mineru-cli"},
        )
        with (
            patch.object(parser.mineru_parser, "parse", return_value=mineru_doc) as mineru_mock,
            patch.object(parser, "_parse_with_pymupdf_text", return_value=[]) as pymupdf_mock,
        ):
            parsed = parser.parse(Path("paper.pdf"))
        self.assertEqual(parsed.metadata.get("parser"), "mineru-cli")
        self.assertEqual(len(parsed.blocks), 1)
        mineru_mock.assert_called_once()
        pymupdf_mock.assert_not_called()

    def test_pdf_parser_falls_back_to_pymupdf_when_mineru_fails(self) -> None:
        parser = PdfParser()
        parser.strategy = "auto"
        parser.enable_mineru = True
        fallback_blocks = [ParsedBlock(text="pymupdf block", section="page-1", page=1)]
        with (
            patch.object(parser.mineru_parser, "parse", side_effect=RuntimeError("mineru failed")),
            patch.object(parser, "_parse_with_pymupdf_text", return_value=fallback_blocks),
        ):
            parsed = parser.parse(Path("paper.pdf"))
        self.assertEqual(parsed.metadata.get("parser"), "pymupdf")
        self.assertEqual(parsed.blocks[0].text, "pymupdf block")

    def test_pdf_parser_uses_sidecar_text_before_ocr(self) -> None:
        parser = PdfParser()
        parser.strategy = "auto"
        parser.enable_mineru = False
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "scan.pdf"
            file_path.write_bytes(b"%PDF-1.4 fake")
            file_path.with_name("scan.pdf.ocr.txt").write_text(
                "page 1\nEntropy measures sample purity.\n\n"
                "\u7b2c 2 \u9875\nInformation gain selects the best split.",
                encoding="utf-8",
            )
            with (
                patch.object(parser, "_parse_with_pymupdf_text", return_value=[]),
                patch.object(parser, "_parse_with_pdfplumber_text", return_value=[]),
                patch.object(parser, "_parse_with_ocr", return_value=[]) as ocr_mock,
            ):
                parsed = parser.parse(file_path)

        self.assertEqual(parsed.metadata.get("parser"), "pdf-sidecar")
        self.assertEqual([block.page for block in parsed.blocks], [1, 2])
        self.assertIn("Entropy measures sample purity.", parsed.blocks[0].text)
        self.assertIn("Information gain selects the best split.", parsed.blocks[1].text)
        ocr_mock.assert_not_called()

    def test_pdf_parser_uses_ocr_when_text_empty(self) -> None:
        parser = PdfParser()
        parser.strategy = "auto"
        parser.enable_mineru = False
        parser.enable_ocr_fallback = True
        ocr_blocks = [ParsedBlock(text="ocr block", section="page-1", page=1)]
        with (
            patch.object(parser, "_parse_with_pymupdf_text", return_value=[]),
            patch.object(parser, "_parse_with_ocr", return_value=ocr_blocks),
        ):
            parsed = parser.parse(Path("scan.pdf"))
        self.assertEqual(parsed.metadata.get("parser"), "pymupdf+paddleocr")
        self.assertEqual(parsed.blocks[0].text, "ocr block")


if __name__ == "__main__":
    unittest.main()
