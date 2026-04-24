from __future__ import annotations

from backend.knowledge.models import KnowledgeChunkDraft
from backend.knowledge.parsers.base import ParsedDocument


class ChunkBuilder:
    def __init__(self, *, max_chars: int = 900, overlap: int = 120) -> None:
        self.max_chars = max(200, int(max_chars))
        self.overlap = max(0, min(self.max_chars // 2, int(overlap)))

    def chunk_document(self, document: ParsedDocument) -> list[KnowledgeChunkDraft]:
        chunks: list[KnowledgeChunkDraft] = []
        chunk_index = 0
        for block in document.blocks:
            text = block.text.strip()
            if not text:
                continue
            for segment in self._split_text(text):
                chunk_index += 1
                chunks.append(
                    KnowledgeChunkDraft(
                        chunk_index=chunk_index,
                        content=segment,
                        source_page=max(0, int(block.page or 0)),
                        source_section=str(block.section or ""),
                        token_estimate=max(1, len(segment) // 4),
                        metadata={**document.metadata, **block.metadata},
                    )
                )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        step = self.max_chars - self.overlap
        segments: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.max_chars)
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
            if end >= len(text):
                break
            start += max(1, step)
        return segments

