from __future__ import annotations

import math
import re


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+")


class HashedTokenEmbedder:
    def __init__(self, *, dimensions: int = 96) -> None:
        self.dimensions = max(16, dimensions)

    def embed_text(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions
        vector = [0.0] * self.dimensions
        for token in tokens:
            index = hash(token) % self.dimensions
            sign = 1.0 if (hash(f"{token}:sign") & 1) == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0.0:
            return vector
        return [value / norm for value in vector]

    def similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=False))

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text or "")]
