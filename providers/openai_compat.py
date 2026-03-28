from __future__ import annotations

import asyncio
import json
import random
import urllib.error
import urllib.request
from typing import Any

from providers.base import LLMProvider, LLMResponse, ToolCallRequest


RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 1.2


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.extra_headers = extra_headers or {}

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

        response = await self._post_json_with_retry(payload)
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI-compatible provider returned no choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCallRequest] = []
        for item in tool_calls_raw:
            function = item.get("function") or {}
            arguments_raw = function.get("arguments") or "{}"
            try:
                arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
            except json.JSONDecodeError:
                arguments = {"raw": arguments_raw}
            tool_calls.append(
                ToolCallRequest(
                    id=str(item.get("id") or function.get("name") or "tool_call"),
                    name=str(function.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {"value": arguments},
                )
            )

        finish_reason = str(choices[0].get("finish_reason") or "stop")
        return LLMResponse(
            content=content if isinstance(content, str) else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw=response,
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.api_base}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                **self.extra_headers,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    async def _post_json_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await asyncio.to_thread(self._post_json, payload)
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in RETRYABLE_HTTP_STATUS_CODES or attempt == MAX_RETRIES:
                    detail = self._read_http_error_body(error)
                    raise RuntimeError(
                        f"OpenAI-compatible provider request failed with HTTP {error.code}: {detail}"
                    ) from error
            except urllib.error.URLError as error:
                last_error = error
                if attempt == MAX_RETRIES:
                    raise RuntimeError(
                        f"OpenAI-compatible provider request failed after retries: {error.reason}"
                    ) from error

            await asyncio.sleep(self._retry_delay_seconds(attempt))

        raise RuntimeError(f"OpenAI-compatible provider request failed: {last_error}")

    @staticmethod
    def _retry_delay_seconds(attempt: int) -> float:
        jitter = random.uniform(0.0, 0.35)
        return BASE_RETRY_DELAY_SECONDS * attempt + jitter

    @staticmethod
    def _read_http_error_body(error: urllib.error.HTTPError) -> str:
        try:
            body = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        return body or error.reason or "unknown error"
