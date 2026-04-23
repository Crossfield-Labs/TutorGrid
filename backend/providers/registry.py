from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.config import PlannerConfig
from backend.providers.base import LLMProvider
from backend.providers.openai_compat import OpenAICompatProvider

_PROVIDER_ALIASES = {
    "aliyun": "openai_compat",
    "dashscope": "openai_compat",
    "deepseek": "openai_compat",
    "glm": "openai_compat",
    "hunyuan": "openai_compat",
    "kimi": "openai_compat",
    "moonshot": "openai_compat",
    "openai": "openai_compat",
    "openai-compatible": "openai_compat",
    "qwen": "openai_compat",
    "siliconflow": "openai_compat",
    "volcengine": "openai_compat",
    "zhipu": "openai_compat",
}

_MODEL_ALIASES = {
    "deepseek": "deepseek-chat",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
    "doubao": "doubao-pro-32k",
    "glm": "glm-4-flash",
    "glm-4": "glm-4-flash",
    "hunyuan": "hunyuan-turbos-latest",
    "kimi": "moonshot-v1-8k",
    "kimi-long": "moonshot-v1-32k",
    "moonshot": "moonshot-v1-8k",
    "qwen": "qwen-plus",
    "qwen-coder": "qwen2.5-coder-32b-instruct",
    "qwen-max": "qwen-max",
}

_PROFILE_DEFAULTS = {
    "dashscope": {"model_aliases": {"qwen": "qwen-plus", "qwen-coder": "qwen-max"}},
    "deepseek": {"extra_body": {"parallel_tool_calls": False}},
    "moonshot": {"model_aliases": {"kimi": "moonshot-v1-8k", "kimi-long": "moonshot-v1-32k"}},
    "qwen": {"model_aliases": {"qwen": "qwen-plus", "qwen-coder": "qwen2.5-coder-32b-instruct"}},
}


@dataclass(slots=True)
class _ResolvedProvider:
    provider_type: str
    model: str
    extra_body: dict[str, Any] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)


class ProviderRegistry:
    @staticmethod
    def create(planner: PlannerConfig) -> LLMProvider:
        resolved = ProviderRegistry.resolve(planner)
        if resolved.provider_type == "openai_compat":
            return OpenAICompatProvider(
                api_key=planner.api_key,
                api_base=planner.api_base,
                model=resolved.model,
                temperature=planner.temperature,
                max_tokens=planner.max_tokens,
                extra_body=resolved.extra_body,
                extra_headers=resolved.extra_headers,
            )
        raise RuntimeError(f"Unsupported planner provider: {planner.provider}")

    @staticmethod
    def resolve(planner: PlannerConfig) -> _ResolvedProvider:
        requested_provider = planner.provider.strip().lower()
        normalized_provider = _PROVIDER_ALIASES.get(requested_provider, requested_provider)
        if normalized_provider != "openai_compat":
            raise RuntimeError(f"Unsupported planner provider: {planner.provider}")

        options = dict(planner.provider_options or {})
        profile_defaults = dict(_PROFILE_DEFAULTS.get(requested_provider, {}))
        model_aliases = dict(_MODEL_ALIASES)
        custom_aliases = options.get("model_aliases")
        if isinstance(profile_defaults.get("model_aliases"), dict):
            model_aliases.update(profile_defaults["model_aliases"])
        if isinstance(custom_aliases, dict):
            model_aliases.update({str(key): str(value) for key, value in custom_aliases.items()})

        requested_model = planner.model.strip()
        resolved_model = model_aliases.get(requested_model.lower(), requested_model)

        extra_body: dict[str, Any] = {}
        profile_extra_body = profile_defaults.get("extra_body")
        if isinstance(profile_extra_body, dict):
            extra_body.update(profile_extra_body)
        configured_extra_body = options.get("extra_body")
        if isinstance(configured_extra_body, dict):
            extra_body.update(configured_extra_body)

        extra_headers = {
            str(key): str(value)
            for key, value in (options.get("extra_headers") or {}).items()
        } if isinstance(options.get("extra_headers"), dict) else {}

        return _ResolvedProvider(
            provider_type=normalized_provider,
            model=resolved_model,
            extra_body=extra_body,
            extra_headers=extra_headers,
        )
