from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = (ROOT / "template" / "scripts").resolve()


class SourcePackageBridgeTests(unittest.TestCase):
    def test_package_bridge_resolves_template_scripts(self) -> None:
        module = importlib.import_module("scripts.validate_contracts")
        module_path = Path(module.__file__).resolve()

        self.assertEqual(TEMPLATE_SCRIPTS, module_path.parent)
        self.assertTrue(callable(module.validate_repository))
        self.assertTrue(callable(module.load_contract_manifest))


if __name__ == "__main__":
    unittest.main()
