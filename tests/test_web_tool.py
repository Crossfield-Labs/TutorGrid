from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

import httpx
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

    def test_web_fetch_returns_graceful_message_on_httpx_403(self) -> None:
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(403, request=request)

        class _FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
                return False

            async def get(self, _url: str) -> httpx.Response:
                raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

        with patch("backend.tools.web.httpx.AsyncClient", return_value=_FakeClient()):
            text = asyncio.run(web_fetch("https://example.com", max_chars=200))

        self.assertIn("[web_fetch unavailable]", text)
        self.assertIn("HTTP 403", text)

    def test_web_fetch_returns_graceful_message_on_stdlib_http_error(self) -> None:
        error = HTTPError(
            url="https://example.com",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )

        with patch("backend.tools.web.httpx", None):
            with patch("backend.tools.web.urlopen", side_effect=error):
                text = asyncio.run(web_fetch("https://example.com", max_chars=200))

        self.assertIn("[web_fetch unavailable]", text)
        self.assertIn("HTTP 403", text)


if __name__ == "__main__":
    unittest.main()
