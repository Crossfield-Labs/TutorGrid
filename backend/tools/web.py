from __future__ import annotations

import httpx


async def web_fetch(url: str, max_chars: int = 12000) -> str:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.text[:max_chars]

