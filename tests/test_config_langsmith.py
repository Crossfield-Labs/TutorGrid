from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.config as config_module


class LangSmithConfigTests(unittest.TestCase):
    def test_update_and_load_langsmith_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            with patch("backend.config._config_path", return_value=config_path):
                config_module.update_langsmith_config(
                    enabled=True,
                    project="pc-orchestrator-tests",
                    api_key="ls-test-key",
                    api_url="https://api.smith.langchain.com",
                )
                loaded = config_module.load_config()
                self.assertTrue(loaded.langsmith.enabled)
                self.assertEqual(loaded.langsmith.project, "pc-orchestrator-tests")
                self.assertEqual(loaded.langsmith.api_key, "ls-test-key")
                self.assertEqual(loaded.langsmith.api_url, "https://api.smith.langchain.com")

                runtime_view = config_module.get_runtime_config_view()
                self.assertIn("langsmith", runtime_view)
                langsmith_view = runtime_view["langsmith"]
                self.assertEqual(langsmith_view["project"], "pc-orchestrator-tests")
                self.assertEqual(langsmith_view["apiKey"], "ls-test-key")

    def test_env_overrides_langsmith_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                '{"langsmith":{"enabled":false,"project":"from-file","apiKey":"file-key","apiUrl":"https://file"}}',
                encoding="utf-8",
            )
            with patch("backend.config._config_path", return_value=config_path):
                with patch.dict(
                    os.environ,
                    {
                        "ORCHESTRATOR_LANGSMITH_ENABLED": "1",
                        "ORCHESTRATOR_LANGSMITH_PROJECT": "from-env",
                        "ORCHESTRATOR_LANGSMITH_API_KEY": "env-key",
                        "ORCHESTRATOR_LANGSMITH_API_URL": "https://env",
                    },
                    clear=False,
                ):
                    loaded = config_module.load_config()
                    self.assertTrue(loaded.langsmith.enabled)
                    self.assertEqual(loaded.langsmith.project, "from-env")
                    self.assertEqual(loaded.langsmith.api_key, "env-key")
                    self.assertEqual(loaded.langsmith.api_url, "https://env")

    def test_update_and_load_search_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            with patch("backend.config._config_path", return_value=config_path):
                config_module.update_search_config(tavily_api_key="tvly-test-key")

                loaded = config_module.load_config()
                self.assertEqual(loaded.search.tavily_api_key, "tvly-test-key")

                runtime_view = config_module.get_runtime_config_view()
                self.assertIn("search", runtime_view)
                self.assertEqual(runtime_view["search"]["tavilyApiKey"], "tvly-test-key")

    def test_env_overrides_search_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"search":{"tavilyApiKey":"file-key"}}', encoding="utf-8")
            with patch("backend.config._config_path", return_value=config_path):
                with patch.dict(os.environ, {"TAVILY_API_KEY": "env-key"}, clear=False):
                    loaded = config_module.load_config()
                    self.assertEqual(loaded.search.tavily_api_key, "env-key")


if __name__ == "__main__":
    unittest.main()
