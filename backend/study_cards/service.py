from __future__ import annotations

import json
import re
from typing import Any

from backend.config import load_config
from backend.providers.registry import ProviderRegistry


class StudyCardGenerationError(RuntimeError):
    pass


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_string(value: Any, max_len: int = 280) -> str:
    return str(value or "").strip()[:max_len]


def _normalize_quiz(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    question = _normalize_string(raw.get("question"), 220)
    raw_options = raw.get("options")
    if not isinstance(raw_options, list):
        return None
    options = [_normalize_string(item, 120) for item in raw_options]
    options = [item for item in options if item]
    try:
        answer = int(raw.get("answer"))
    except (TypeError, ValueError):
        return None
    explanation = _normalize_string(raw.get("explanation"), 360)
    if not question or len(options) < 2 or answer < 0 or answer >= len(options):
        return None
    return {
        "question": question,
        "options": options[:6],
        "answer": answer,
        "explanation": explanation,
    }


def _normalize_flashcards(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    cards: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        front = _normalize_string(item.get("front"), 160)
        back = _normalize_string(item.get("back"), 320)
        if front and back:
            cards.append({"front": front, "back": back})
    return cards[:6]


def parse_study_cards_response(text: str) -> dict[str, Any]:
    parsed = _extract_json_object(text)
    return {
        "quiz": _normalize_quiz(parsed.get("quiz")),
        "flashcards": _normalize_flashcards(parsed.get("flashcards")),
    }


class StudyCardService:
    def __init__(self) -> None:
        self.config = load_config()
        self.provider = ProviderRegistry.create(self.config.planner)

    async def generate(
        self,
        *,
        source_text: str,
        course_id: str = "",
        doc_id: str = "",
        language: str = "zh-CN",
    ) -> dict[str, Any]:
        normalized_source = str(source_text or "").strip()
        if not normalized_source:
            raise StudyCardGenerationError("source_text is required")

        prompt = (
            "请根据给定学习材料生成一个选择题和 3-5 张闪卡。"
            "必须只输出 JSON，不要 Markdown，不要额外解释。"
            "JSON 结构："
            '{"quiz":{"question":"...","options":["..."],"answer":0,"explanation":"..."},'
            '"flashcards":[{"front":"...","back":"..."}]}。'
            "answer 使用从 0 开始的选项下标。"
            f"输出语言：{language}。\n\n"
            f"course_id={course_id}\n"
            f"doc_id={doc_id}\n"
            f"学习材料：\n{normalized_source[:6000]}"
        )
        try:
            response = await self.provider.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "你是学习卡片生成器，只返回严格 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=None,
            )
        except Exception as exc:
            raise StudyCardGenerationError(f"AI 生成学习卡片失败：{exc}") from exc

        result = parse_study_cards_response(str(response.content or ""))
        if result["quiz"] is None and not result["flashcards"]:
            raise StudyCardGenerationError("AI 返回内容无法解析为测验/闪卡 JSON")
        return result
