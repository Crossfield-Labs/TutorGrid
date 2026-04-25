from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.tools.web import web_fetch


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self._data = text.encode("utf-8")
        self.headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

    def read(self, _max_bytes: int | None = None) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


class WebToolTests(unittest.TestCase):
    def test_web_fetch_falls_back_to_stdlib_when_httpx_unavailable(self) -> None:
        fake_response = _FakeResponse("example content from stdlib fallback")

        with patch("backend.tools.web.httpx", None):
            with patch("backend.tools.web.urlopen", return_value=fake_response):
                text = asyncio.run(web_fetch("https://example.com", max_chars=20))

        self.assertEqual(text, "example content from")


if __name__ == "__main__":
    unittest.main()
