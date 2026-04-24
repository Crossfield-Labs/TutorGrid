from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Any


@dataclass(slots=True)
class RagEvalCase:
    question: str
    expected_phrases: list[str] = field(default_factory=list)
    limit: int = 8
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RagEvalResult:
    question: str
    expected_phrases: list[str]
    first_relevant_rank: int | None
    retrieved_count: int
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


def find_first_relevant_rank(items: list[dict[str, Any]], expected_phrases: list[str]) -> int | None:
    normalized_phrases = [item.strip().lower() for item in expected_phrases if item.strip()]
    if not normalized_phrases:
        return None
    for index, item in enumerate(items, start=1):
        content = str(item.get("content") or "").lower()
        if any(phrase in content for phrase in normalized_phrases):
            return index
    return None


def aggregate_rag_metrics(results: list[RagEvalResult], *, ks: list[int]) -> dict[str, Any]:
    safe_ks = sorted({max(1, int(k)) for k in ks}) or [1, 3, 5]
    total = len(results)
    if total <= 0:
        return {
            "totalQueries": 0,
            "mrr": 0.0,
            "meanLatencyMs": 0.0,
            "recallAtK": {f"R@{k}": 0.0 for k in safe_ks},
            "hitCountAtK": {f"R@{k}": 0 for k in safe_ks},
        }
    reciprocal_sum = 0.0
    hit_count_map: dict[int, int] = {k: 0 for k in safe_ks}
    for item in results:
        rank = item.first_relevant_rank
        if rank is not None and rank > 0:
            reciprocal_sum += 1.0 / float(rank)
            for k in safe_ks:
                if rank <= k:
                    hit_count_map[k] += 1
    mean_latency = fmean([float(item.latency_ms) for item in results])
    recall_map = {f"R@{k}": hit_count_map[k] / float(total) for k in safe_ks}
    return {
        "totalQueries": total,
        "mrr": reciprocal_sum / float(total),
        "meanLatencyMs": mean_latency,
        "recallAtK": recall_map,
        "hitCountAtK": {f"R@{k}": hit_count_map[k] for k in safe_ks},
    }
