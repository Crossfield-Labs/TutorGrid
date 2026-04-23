from __future__ import annotations

import asyncio
import json
import random
import ssl
import time
import urllib.error
import urllib.request
from typing import Any
from typing import Callable

from backend.providers.base import LLMProvider, LLMResponse, TextStreamCallback, ToolCallRequest


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        extra_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.extra_body = dict(extra_body or {})
        self.extra_headers = dict(extra_headers or {})
        self.max_retries = 3
        self.retry_backoff_seconds = 1.0
        self.circuit_breaker_threshold = 3
        self.circuit_breaker_cooldown_seconds = 30.0
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_text_delta: TextStreamCallback | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if self.extra_body:
            payload.update(self.extra_body)
        should_stream = on_text_delta is not None and not tools
        if should_stream:
            payload["stream"] = True
            response = await self._post_json_stream_with_retry(payload, on_text_delta=on_text_delta)
        else:
            response = await self._post_json_with_retry(payload)
        choices = response.get("choices") or []
        message = choices[0].get("message") if choices else {}
        tool_calls_raw = message.get("tool_calls") if isinstance(message, dict) else []
        tool_calls: list[ToolCallRequest] = []
        for item in tool_calls_raw or []:
            function = item.get("function") if isinstance(item, dict) else {}
            arguments_raw = function.get("arguments") if isinstance(function, dict) else "{}"
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
        return LLMResponse(
            content=message.get("content") if isinstance(message, dict) else None,
            tool_calls=tool_calls,
            finish_reason=str(choices[0].get("finish_reason") or "stop") if choices else "stop",
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
                **self.extra_headers,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json_stream(self, payload: dict[str, Any], *, on_text_delta: Callable[[str], None]) -> dict[str, Any]:
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
        content_parts: list[str] = []
        finish_reason = "stop"
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                for choice in event.get("choices") or []:
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        content_parts.append(content)
                        on_text_delta(content)
                    finish_reason = str(choice.get("finish_reason") or finish_reason)
        return {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {
                        "role": "assistant",
                        "content": "".join(content_parts),
                    },
                }
            ]
        }

    async def _post_json_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._raise_if_circuit_open()
        last_message = "unknown provider failure"
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await asyncio.to_thread(self._post_json, payload)
            except urllib.error.HTTPError as error:
                detail = self._read_http_error(error)
                last_message = f"HTTP {error.code}: {detail}"
                if attempt < self.max_retries and self._is_retryable_status(error.code):
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                self._record_failure()
                raise RuntimeError(
                    f"OpenAI-compatible provider request failed after {attempt} attempt(s): {last_message}"
                ) from error
            except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError) as error:
                last_message = str(error)
                if attempt < self.max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                self._record_failure()
                raise RuntimeError(
                    f"OpenAI-compatible provider request failed after {attempt} attempt(s): {last_message}"
                ) from error
            else:
                self._reset_failure_state()
                return response
        self._record_failure()
        raise RuntimeError(
            f"OpenAI-compatible provider request failed after {self.max_retries} attempt(s): {last_message}"
        )

    async def _post_json_stream_with_retry(
        self,
        payload: dict[str, Any],
        *,
        on_text_delta: TextStreamCallback,
    ) -> dict[str, Any]:
        self._raise_if_circuit_open()
        last_message = "unknown provider failure"
        loop = asyncio.get_running_loop()
        delta_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def enqueue_delta(text: str) -> None:
            loop.call_soon_threadsafe(delta_queue.put_nowait, text)

        async def drain_deltas() -> None:
            while True:
                item = await delta_queue.get()
                if item is None:
                    break
                await on_text_delta(item)

        for attempt in range(1, self.max_retries + 1):
            request_task: asyncio.Task[dict[str, Any]] | None = None
            drain_task: asyncio.Task[None] | None = None
            try:
                request_task = asyncio.create_task(
                    asyncio.to_thread(self._post_json_stream, payload, on_text_delta=enqueue_delta)
                )
                drain_task = asyncio.create_task(drain_deltas())
                response = await request_task
                await delta_queue.put(None)
                await drain_task
            except urllib.error.HTTPError as error:
                await delta_queue.put(None)
                if drain_task is not None:
                    await drain_task
                detail = self._read_http_error(error)
                last_message = f"HTTP {error.code}: {detail}"
                if attempt < self.max_retries and self._is_retryable_status(error.code):
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                self._record_failure()
                raise RuntimeError(
                    f"OpenAI-compatible provider stream request failed after {attempt} attempt(s): {last_message}"
                ) from error
            except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError, json.JSONDecodeError) as error:
                await delta_queue.put(None)
                if drain_task is not None:
                    await drain_task
                last_message = str(error)
                if attempt < self.max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                self._record_failure()
                raise RuntimeError(
                    f"OpenAI-compatible provider stream request failed after {attempt} attempt(s): {last_message}"
                ) from error
            except Exception:
                await delta_queue.put(None)
                if drain_task is not None:
                    await drain_task
                raise
            else:
                self._reset_failure_state()
                return response
        self._record_failure()
        raise RuntimeError(
            f"OpenAI-compatible provider stream request failed after {self.max_retries} attempt(s): {last_message}"
        )

    def _retry_delay(self, attempt: int) -> float:
        base = self.retry_backoff_seconds * (2 ** max(0, attempt - 1))
        return base + random.uniform(0.0, 0.25)

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    def _read_http_error(self, error: urllib.error.HTTPError) -> str:
        try:
            payload = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            payload = ""
        return payload or str(error.reason or "request failed")

    def _raise_if_circuit_open(self) -> None:
        if self._circuit_open_until <= 0.0:
            return
        remaining = self._circuit_open_until - time.monotonic()
        if remaining > 0:
            raise RuntimeError(
                f"Planner provider circuit is open for another {remaining:.1f}s after repeated API failures."
            )
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self.circuit_breaker_threshold:
            return
        self._circuit_open_until = time.monotonic() + self.circuit_breaker_cooldown_seconds
        self._consecutive_failures = 0

    def _reset_failure_state(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0


