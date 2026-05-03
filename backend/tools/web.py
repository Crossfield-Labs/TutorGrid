from __future__ import annotations

import asyncio
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments.
    httpx = None


async def web_fetch(url: str, max_chars: int = 12000) -> str:
    if httpx is not None:
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "TutorGrid/1.0"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            return response.text[:max_chars]
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            return _graceful_fetch_failure(
                url=url,
                reason=f"HTTP {status_code}",
                suggestion="该站点拒绝访问，建议改用其他来源继续整理。",
                max_chars=max_chars,
            )
        except httpx.HTTPError as exc:
            return _graceful_fetch_failure(
                url=url,
                reason=str(exc),
                suggestion="网络请求失败，建议改用其他来源或基于现有证据继续回答。",
                max_chars=max_chars,
            )

    def _fetch_with_stdlib() -> str:
        request = Request(url, headers={"User-Agent": "pc-orchestrator/1.0"})
        try:
            with urlopen(request, timeout=15.0) as response:
                data = response.read(1_000_000)
                charset = response.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")
        except HTTPError as exc:
            return _graceful_fetch_failure(
                url=url,
                reason=f"HTTP {exc.code}",
                suggestion="该站点拒绝访问，建议改用其他来源继续整理。",
                max_chars=max_chars,
            )
        except URLError as exc:
            return _graceful_fetch_failure(
                url=url,
                reason=str(exc.reason),
                suggestion="网络请求失败，建议改用其他来源或基于现有证据继续回答。",
                max_chars=max_chars,
            )

    text = await asyncio.to_thread(_fetch_with_stdlib)
    return text[:max_chars]


def _graceful_fetch_failure(*, url: str, reason: str, suggestion: str, max_chars: int) -> str:
    message = (
        f"[web_fetch unavailable]\n"
        f"url: {url}\n"
        f"reason: {reason}\n"
        f"suggestion: {suggestion}"
    )
    return message[:max_chars]

