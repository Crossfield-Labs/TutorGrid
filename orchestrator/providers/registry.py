from __future__ import annotations

from orchestrator.config import PlannerConfig
from orchestrator.providers.base import LLMProvider
from orchestrator.providers.openai_compat import OpenAICompatProvider


class ProviderRegistry:
    @staticmethod
    def create(planner: PlannerConfig) -> LLMProvider:
        provider_type = planner.provider.strip().lower()
        if provider_type in {"openai_compat", "openai-compatible", "openai"}:
            return OpenAICompatProvider(
                api_key=planner.api_key,
                api_base=planner.api_base,
                model=planner.model,
                temperature=planner.temperature,
                max_tokens=planner.max_tokens,
            )
        raise RuntimeError(f"Unsupported planner provider: {planner.provider}")
