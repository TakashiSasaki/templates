from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPTS = (ROOT / "scripts").resolve()
TEMPLATE_SCRIPTS = (ROOT / "template" / "scripts").resolve()


class SourcePackageBridgeTests(unittest.TestCase):
    def test_package_bridge_resolves_template_scripts(self) -> None:
        module = importlib.import_module("scripts.validate_contracts")
        module_path = Path(module.__file__).resolve()

        self.assertEqual(TEMPLATE_SCRIPTS, module_path.parent)
        self.assertTrue(callable(module.validate_repository))
        self.assertTrue(callable(module.load_contract_manifest))

    def test_package_bridge_coexists_with_source_only_scripts(self) -> None:
        source_module = importlib.import_module("scripts.validate_distribution")
        canonical_module = importlib.import_module("scripts.validate_contracts")

        self.assertEqual(SOURCE_SCRIPTS, Path(source_module.__file__).resolve().parent)
        self.assertEqual(
            TEMPLATE_SCRIPTS,
            Path(canonical_module.__file__).resolve().parent,
        )
        self.assertTrue(callable(source_module.validate_distribution))
        self.assertTrue(callable(canonical_module.validate_repository))


if __name__ == "__main__":
    unittest.main()
