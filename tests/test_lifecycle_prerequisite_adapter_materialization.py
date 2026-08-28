from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components/lifecycle.composition-state/component.json"
ADAPTER = ROOT / "components/lifecycle.composition-state/files/.template-composition/validate.py"
IMPLEMENTATION = ROOT / "components/lifecycle.composition-state/files/.template-composition/validate_impl.py"


class LifecyclePrerequisiteAdapterMaterializationTests(unittest.TestCase):
    def test_adapter_and_preserved_validation_implementation_are_managed(self) -> None:
        component = json.loads(COMPONENT.read_text(encoding="utf-8"))
        self.assertEqual(component["version"], 16)
        materials = {
            entry["destination"]: entry["ownership"]
            for entry in component["materials"]
        }
        self.assertEqual(materials[".template-composition/validate.py"], "managed")
        self.assertEqual(materials[".template-composition/validate_impl.py"], "managed")
        self.assertTrue(ADAPTER.is_file())
        self.assertTrue(IMPLEMENTATION.is_file())

    def test_adapter_delegates_validation_authority_instead_of_copying_runtime_logic(self) -> None:
        adapter = ADAPTER.read_text(encoding="utf-8")
        self.assertIn('with_name("validate_impl.py")', adapter)
        self.assertIn("_impl._validate_base(root)", adapter)
        self.assertNotIn("def _ensure_validation_python", adapter)
        self.assertNotIn("def _build_validation_runtime", adapter)


if __name__ == "__main__":
    unittest.main()
