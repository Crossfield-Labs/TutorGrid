from __future__ import annotations

import json
import math
import re
import ssl
import time
import urllib.error
import urllib.request
from typing import Protocol


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+")


class TextEmbedder(Protocol):
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=False))

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text or "")]


class OpenAICompatEmbedder:
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str = "text-embedding-3-large",
        max_retries: int = 3,
        batch_size: int = 32,
        timeout_seconds: int = 90,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.model = model.strip() or "text-embedding-3-large"
        self.max_retries = max(1, int(max_retries))
        self.batch_size = max(1, int(batch_size))
        self.timeout_seconds = max(15, int(timeout_seconds))

    def embed_text(self, text: str) -> list[float]:
        result = self.embed_texts([text])
        return result[0] if result else []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized = [str(item or "").strip() for item in texts]
        if not normalized:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self.batch_size):
            batch = normalized[start : start + self.batch_size]
            vectors.extend(self._request_embeddings_with_retry(batch))
        return vectors

    def _request_embeddings_with_retry(self, inputs: list[str]) -> list[list[float]]:
        last_message = "unknown embedding provider failure"
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._request_embeddings(inputs)
            except urllib.error.HTTPError as error:
                detail = self._read_http_error(error)
                last_message = f"HTTP {error.code}: {detail}"
                if attempt >= self.max_retries or not self._is_retryable_status(error.code):
                    raise RuntimeError(
                        f"Embedding request failed after {attempt} attempt(s): {last_message}"
                    ) from error
            except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError) as error:
                last_message = str(error)
                if attempt >= self.max_retries:
                    raise RuntimeError(
                        f"Embedding request failed after {attempt} attempt(s): {last_message}"
                    ) from error
            time.sleep(min(1.5, 0.25 * attempt))
        raise RuntimeError(f"Embedding request failed after {self.max_retries} attempt(s): {last_message}")

    def _request_embeddings(self, inputs: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": inputs}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.api_base}/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        data = parsed.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Embedding response missing data field.")
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0)
        vectors: list[list[float]] = []
        for item in ordered:
            if not isinstance(item, dict):
                continue
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                continue
            vectors.append([float(value) for value in embedding])
        if len(vectors) != len(inputs):
            raise RuntimeError("Embedding response size does not match input size.")
        return vectors

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    @staticmethod
    def _read_http_error(error: urllib.error.HTTPError) -> str:
        try:
            payload = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            payload = ""
        return payload or str(error.reason or "request failed")
