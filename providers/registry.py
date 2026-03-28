from __future__ import annotations

from providers.base import LLMProvider
from providers.openai_compat import OpenAICompatProvider


class ProviderRegistry:
    @staticmethod
    def create(
        *,
        provider_type: str,
        api_key: str,
        api_base: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMProvider:
        normalized = provider_type.strip().lower()
        if normalized in {"openai_compat", "openai-compatible", "openai"}:
            if not api_key.strip():
                raise RuntimeError("Missing planner API key for openai_compat provider.")
            if not api_base.strip():
                raise RuntimeError("Missing planner API base for openai_compat provider.")
            if not model.strip():
                raise RuntimeError("Missing planner model for openai_compat provider.")
            return OpenAICompatProvider(
                api_key=api_key.strip(),
                api_base=api_base.strip(),
                model=model.strip(),
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise RuntimeError(f"Unsupported planner provider: {provider_type}")
