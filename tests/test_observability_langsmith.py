from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import backend.observability.langsmith as langsmith_module


def _mock_config(*, enabled: bool, project: str, api_key: str = "", api_url: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        langsmith=SimpleNamespace(
            enabled=enabled,
            project=project,
            api_key=api_key,
            api_url=api_url,
        )
    )


class LangSmithTracerTests(unittest.TestCase):
    def test_tracer_disabled_when_config_disabled(self) -> None:
        with patch("backend.observability.langsmith.load_config", return_value=_mock_config(enabled=False, project="p")):
            tracer = langsmith_module.LangSmithTracer()
            self.assertFalse(tracer.enabled)
            self.assertIsNone(tracer.client)
            self.assertEqual(tracer.project_name, "p")

    def test_get_and_reset_langsmith_tracer(self) -> None:
        with patch("backend.observability.langsmith.load_config", return_value=_mock_config(enabled=False, project="p")):
            langsmith_module.reset_langsmith_tracer()
            tracer_1 = langsmith_module.get_langsmith_tracer()
            tracer_2 = langsmith_module.get_langsmith_tracer()
            self.assertIs(tracer_1, tracer_2)

            langsmith_module.reset_langsmith_tracer()
            tracer_3 = langsmith_module.get_langsmith_tracer()
            self.assertIsNot(tracer_1, tracer_3)


if __name__ == "__main__":
    unittest.main()
