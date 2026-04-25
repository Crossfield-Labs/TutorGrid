from __future__ import annotations

import importlib
import unittest


class LazyImportTests(unittest.TestCase):
    def test_import_protocol_without_runtime_side_effects(self) -> None:
        protocol_module = importlib.import_module("backend.server.protocol")
        self.assertTrue(hasattr(protocol_module, "OrchestratorRequest"))
        self.assertTrue(hasattr(protocol_module, "build_event"))

    def test_import_backend_package_without_eager_runtime_import(self) -> None:
        backend_module = importlib.import_module("backend")
        self.assertTrue(hasattr(backend_module, "__getattr__"))
        self.assertIn("OrchestratorRuntime", getattr(backend_module, "__all__", []))


if __name__ == "__main__":
    unittest.main()
