from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any

from orchestrator.providers.base import LLMProvider, LLMResponse


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        response = await asyncio.to_thread(self._post_json, payload)
        choices = response.get("choices") or []
        message = choices[0].get("message") if choices else {}
        return LLMResponse(
            content=message.get("content") if isinstance(message, dict) else None,
            raw=response if isinstance(response, dict) else {},
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.api_base}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
