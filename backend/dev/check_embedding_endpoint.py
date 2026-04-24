from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.config import load_config


@dataclass
class EndpointCheckResult:
    name: str
    ok: bool
    attempts: int
    status_code: int | None
    detail: str
    response_preview: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check embedding/chat endpoint availability before backend startup.")
    parser.add_argument("--api-base", default="", help="OpenAI-compatible API base URL.")
    parser.add_argument("--api-key", default="", help="API key for the endpoint.")
    parser.add_argument(
        "--embedding-model",
        default="",
        help="Embedding model name to verify (default: env/config/or text-embedding-3-large).",
    )
    parser.add_argument("--chat-model", default="", help="Optional chat model name for extra check.")
    parser.add_argument("--check-chat", action="store_true", help="Also verify /chat/completions.")
    parser.add_argument("--require-chat", action="store_true", help="Fail when chat check does not pass.")
    parser.add_argument("--retries", type=int, default=3, help="Retries per endpoint.")
    parser.add_argument("--timeout", type=int, default=45, help="Request timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    return parser.parse_args()


def _resolve_runtime(args: argparse.Namespace) -> dict[str, str]:
    config = load_config()
    planner = config.planner
    api_base = (
        args.api_base.strip()
        or os.environ.get("ORCHESTRATOR_EMBEDDING_API_BASE", "").strip()
        or planner.api_base.strip()
    )
    api_key = (
        args.api_key.strip()
        or os.environ.get("ORCHESTRATOR_EMBEDDING_API_KEY", "").strip()
        or planner.api_key.strip()
    )
    embedding_model = (
        args.embedding_model.strip()
        or os.environ.get("ORCHESTRATOR_EMBEDDING_MODEL", "").strip()
        or "text-embedding-3-large"
    )
    chat_model = (
        args.chat_model.strip()
        or os.environ.get("ORCHESTRATOR_PLANNER_MODEL", "").strip()
        or planner.model.strip()
    )
    return {
        "api_base": api_base.rstrip("/"),
        "api_key": api_key,
        "embedding_model": embedding_model,
        "chat_model": chat_model,
    }


def _request_json(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None,
    timeout: int,
) -> tuple[int | None, dict[str, Any], str, str]:
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=max(5, int(timeout))) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {}
            return int(getattr(response, "status", 0) or 0), parsed, raw, ""
    except urllib.error.HTTPError as error:
        raw = ""
        try:
            raw = error.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(error)
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {}
        return int(error.code), parsed, raw, ""
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError) as error:
        return None, {}, "", str(error).strip() or type(error).__name__


def _preview(text: str, limit: int = 240) -> str:
    normalized = (text or "").replace("\n", " ").strip()
    return normalized[:limit]


def _embedding_ok(parsed: dict[str, Any]) -> bool:
    data = parsed.get("data")
    if not isinstance(data, list) or not data:
        return False
    first = data[0]
    if not isinstance(first, dict):
        return False
    embedding = first.get("embedding")
    return isinstance(embedding, list) and len(embedding) > 0


def _chat_ok(parsed: dict[str, Any]) -> bool:
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    message = first.get("message")
    if not isinstance(message, dict):
        return False
    content = str(message.get("content") or "").strip()
    return bool(content)


def _check_with_retry(
    *,
    name: str,
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None,
    timeout: int,
    retries: int,
    validator: Any,
) -> EndpointCheckResult:
    attempts = max(1, int(retries))
    last_status: int | None = None
    last_detail = ""
    last_preview = ""
    for attempt in range(1, attempts + 1):
        status_code, parsed, raw, network_error = _request_json(
            method=method,
            url=url,
            api_key=api_key,
            payload=payload,
            timeout=timeout,
        )
        last_status = status_code
        last_preview = _preview(raw)
        if network_error:
            last_detail = f"network_error: {network_error}"
        elif status_code is None:
            last_detail = "no_response"
        elif status_code < 200 or status_code >= 300:
            error_message = str(parsed.get("error") or "").strip()
            last_detail = f"http_{status_code}: {error_message or last_preview or 'request failed'}"
        elif validator(parsed):
            return EndpointCheckResult(
                name=name,
                ok=True,
                attempts=attempt,
                status_code=status_code,
                detail="ok",
                response_preview=last_preview,
            )
        else:
            last_detail = "invalid_response_shape"
        if attempt < attempts:
            time.sleep(min(2.0, 0.6 * attempt))
    return EndpointCheckResult(
        name=name,
        ok=False,
        attempts=attempts,
        status_code=last_status,
        detail=last_detail or "failed",
        response_preview=last_preview,
    )


def _print_human(results: list[EndpointCheckResult], runtime: dict[str, str]) -> None:
    print(f"apiBase={runtime['api_base']}")
    print(f"embeddingModel={runtime['embedding_model']}")
    if runtime["chat_model"]:
        print(f"chatModel={runtime['chat_model']}")
    for result in results:
        state = "PASS" if result.ok else "FAIL"
        code = result.status_code if result.status_code is not None else "-"
        print(f"[{state}] {result.name} attempts={result.attempts} status={code} detail={result.detail}")
        if result.response_preview:
            print(f"  preview={result.response_preview}")


def main() -> None:
    args = parse_args()
    if args.require_chat and not args.check_chat:
        print("--require-chat requires --check-chat.", file=sys.stderr)
        raise SystemExit(2)
    runtime = _resolve_runtime(args)
    if not runtime["api_base"] or not runtime["api_key"]:
        print("Missing API base or key. Provide --api-base/--api-key or set env/config first.", file=sys.stderr)
        raise SystemExit(2)
    if not runtime["embedding_model"]:
        print("Missing embedding model name.", file=sys.stderr)
        raise SystemExit(2)

    results: list[EndpointCheckResult] = []
    embedding_result = _check_with_retry(
        name="embeddings",
        method="POST",
        url=f"{runtime['api_base']}/embeddings",
        api_key=runtime["api_key"],
        payload={"model": runtime["embedding_model"], "input": ["embedding health check"]},
        timeout=int(args.timeout),
        retries=int(args.retries),
        validator=_embedding_ok,
    )
    results.append(embedding_result)

    chat_result: EndpointCheckResult | None = None
    if args.check_chat:
        if not runtime["chat_model"]:
            chat_result = EndpointCheckResult(
                name="chat.completions",
                ok=False,
                attempts=0,
                status_code=None,
                detail="chat_model_missing",
                response_preview="",
            )
        else:
            chat_result = _check_with_retry(
                name="chat.completions",
                method="POST",
                url=f"{runtime['api_base']}/chat/completions",
                api_key=runtime["api_key"],
                payload={
                    "model": runtime["chat_model"],
                    "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
                    "temperature": 0,
                    "max_tokens": 16,
                },
                timeout=int(args.timeout),
                retries=int(args.retries),
                validator=_chat_ok,
            )
        results.append(chat_result)

    passed = embedding_result.ok and (chat_result.ok if (args.check_chat and args.require_chat and chat_result is not None) else True)
    summary = {
        "ok": passed,
        "apiBase": runtime["api_base"],
        "embeddingModel": runtime["embedding_model"],
        "chatModel": runtime["chat_model"],
        "results": [
            {
                "name": item.name,
                "ok": item.ok,
                "attempts": item.attempts,
                "statusCode": item.status_code,
                "detail": item.detail,
                "responsePreview": item.response_preview,
            }
            for item in results
        ],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_human(results, runtime)
        print(f"overall={'PASS' if passed else 'FAIL'}")
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
