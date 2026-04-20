import json
import os
import random
import re
import subprocess
import time
from pathlib import Path

import requests


GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PR_NUMBER = os.environ["PR_NUMBER"]
REPO = os.environ["REPO"]

PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = [
    m for m in [
        os.environ.get("GEMINI_FALLBACK_MODEL_1", "gemini-2.0-flash"),
    ] if m
]

DIFF_PATH = Path("pr.diff")
MAX_DIFF_CHARS = 60000


def redact_secrets(text: str) -> str:
    """Redact API keys and key query params from any text."""
    if not text:
        return text

    redacted = text

    # Redact Google API keys that often start with AIza
    redacted = re.sub(r"AIza[0-9A-Za-z\-_]+", "***REDACTED_API_KEY***", redacted)

    # Redact query-string style keys: ?key=... or &key=...
    redacted = re.sub(r"([?&]key=)[^&\s]+", r"\1***REDACTED***", redacted)

    # Generic bearer/token-like patterns in case future debugging includes them
    redacted = re.sub(
        r"(?i)(authorization:\s*bearer\s+)[^\s]+",
        r"\1***REDACTED***",
        redacted,
    )

    return redacted


def run_command(args: list[str]) -> None:
    subprocess.run(args, check=True)


def post_comment(body: str) -> None:
    run_command([
        "gh",
        "pr",
        "comment",
        PR_NUMBER,
        "--repo",
        REPO,
        "--body",
        body,
    ])


def safe_json_dumps(data: object, max_len: int = 3000) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        text = str(data)
    return redact_secrets(text[:max_len])


def read_diff() -> str:
    if not DIFF_PATH.exists():
        return ""
    return DIFF_PATH.read_text(encoding="utf-8", errors="ignore")


def build_prompt(diff_text: str) -> str:
    truncated = diff_text[:MAX_DIFF_CHARS]

    return f"""
你是资深代码审查员。请只指出“值得人工进一步确认”的问题，不要罗列格式、命名、排版问题。

重点关注：
1. 安全风险
2. 逻辑 bug
3. 边界条件
4. 可能的 breaking change
5. 测试缺失
6. CI / workflow / deploy 风险

要求：
- 只有在确实值得人工确认时才提问
- 不要为了评论而评论
- 最多 3 个问题
- 输出中文 Markdown
- 如果没有明显问题，也要给出简短总结，但不要硬凑问题

输出格式：

## AI Review Summary
- 一句话总结这次改动
- 风险等级：低 / 中 / 高

## Questions
- 最多列出 3 个值得作者确认的问题
- 每条写清楚：
  - 文件
  - 风险点
  - 你想问作者的问题

如果没有明显问题，就写：
- 暂未发现明显高风险改动，建议人工快速检查关键逻辑和测试覆盖。

以下是 PR diff：

{truncated}
""".strip()


def call_gemini(model: str, prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    max_attempts = 4
    base_sleep = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, timeout=120)

            if resp.status_code in (500, 503):
                last_error = f"HTTP {resp.status_code}: Gemini service temporarily unavailable"
                if attempt < max_attempts:
                    sleep_s = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
                    time.sleep(sleep_s)
                    continue

            if resp.status_code == 429:
                last_error = "HTTP 429: rate limit reached"
                if attempt < max_attempts:
                    sleep_s = max(15, base_sleep * (2 ** attempt)) + random.uniform(0, 2)
                    time.sleep(sleep_s)
                    continue

            if resp.status_code >= 400:
                # Keep details minimal and redacted; don't leak URL or key
                response_preview = redact_secrets(resp.text[:800])
                raise RuntimeError(
                    f"HTTP {resp.status_code} from Gemini API. "
                    f"Response preview: {response_preview}"
                )

            data = resp.json()

            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
            except Exception:
                return (
                    "## AI Review Summary\n"
                    "- AI returned an unexpected response shape.\n\n"
                    "<details>\n"
                    "<summary>Debug details</summary>\n\n"
                    "```json\n"
                    f"{safe_json_dumps(data)}\n"
                    "```\n"
                    "</details>"
                )

        except requests.RequestException as exc:
            last_error = redact_secrets(str(exc))
            if attempt < max_attempts:
                sleep_s = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
                time.sleep(sleep_s)
                continue
            break
        except Exception as exc:
            last_error = redact_secrets(str(exc))
            if attempt < max_attempts:
                sleep_s = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
                time.sleep(sleep_s)
                continue
            break

    raise RuntimeError(f"Model {model} failed after retries: {last_error}")


def generate_review() -> str:
    diff_text = read_diff()

    if not diff_text.strip():
        return "## AI Review Summary\n- No diff found for this PR."

    prompt = build_prompt(diff_text)

    models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
    errors: list[str] = []

    for model in models_to_try:
        try:
            result = call_gemini(model, prompt)
            return f"{result}\n\n_Used model: `{model}`_"
        except Exception as exc:
            errors.append(f"- {model}: {redact_secrets(str(exc))}")

    error_block = "\n".join(errors[:10])

    return (
        "## AI Review Summary\n"
        "- AI review could not be completed this time.\n\n"
        "## Notes\n"
        "- Gemini API returned temporary errors or rate limits after retries.\n"
        "- This usually indicates service pressure or free-tier throttling, not necessarily a problem with your PR.\n"
        "- Try rerunning the workflow later or testing with a smaller PR.\n\n"
        "<details>\n"
        "<summary>Debug details</summary>\n\n"
        f"{error_block}\n"
        "</details>"
    )


def main() -> None:
    review_text = generate_review()

    body = f"""{review_text}

---
_Auto-generated by Gemini PR review workflow._
"""

    post_comment(body)


if __name__ == "__main__":
    main()