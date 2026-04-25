from __future__ import annotations

import asyncio
from urllib.request import Request, urlopen

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments.
    httpx = None


async def web_fetch(url: str, max_chars: int = 12000) -> str:
    if httpx is not None:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.text[:max_chars]

    def _fetch_with_stdlib() -> str:
        request = Request(url, headers={"User-Agent": "pc-orchestrator/1.0"})
        with urlopen(request, timeout=15.0) as response:
            data = response.read(1_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")

    text = await asyncio.to_thread(_fetch_with_stdlib)
    return text[:max_chars]

