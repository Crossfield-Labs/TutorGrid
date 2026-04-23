from __future__ import annotations

import unittest

from backend.config import PlannerConfig
from backend.providers.openai_compat import OpenAICompatProvider
from backend.providers.registry import ProviderRegistry


class ProviderRegistryTests(unittest.TestCase):
    def test_domestic_provider_alias_uses_openai_compat_profile(self) -> None:
        provider = ProviderRegistry.create(
            PlannerConfig(
                provider="qwen",
                model="qwen",
                api_key="key",
                api_base="https://example.test/v1",
            )
        )

        self.assertIsInstance(provider, OpenAICompatProvider)
        self.assertEqual(provider.model, "qwen-plus")

    def test_provider_options_override_model_alias_and_headers(self) -> None:
        provider = ProviderRegistry.create(
            PlannerConfig(
                provider="deepseek",
                model="deepseek",
                api_key="key",
                api_base="https://example.test/v1",
                provider_options={
                    "model_aliases": {"deepseek": "deepseek-v3-custom"},
                    "extra_headers": {"X-Test": "yes"},
                    "extra_body": {"stream": False},
                },
            )
        )

        self.assertIsInstance(provider, OpenAICompatProvider)
        self.assertEqual(provider.model, "deepseek-v3-custom")
        self.assertEqual(provider.extra_headers["X-Test"], "yes")
        self.assertFalse(provider.extra_body["stream"])
        self.assertFalse(provider.extra_body["parallel_tool_calls"])


if __name__ == "__main__":
    unittest.main()
