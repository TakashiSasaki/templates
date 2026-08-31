from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SharedWebSourceClosureTests(unittest.TestCase):
    def test_shared_web_contracts_have_one_foundation_authority(self) -> None:
        webapp = ROOT / "components" / "artifact.webapp-core" / "files"
        foundation = ROOT / "components" / "foundation.web" / "files"
        for name in ("browser-identity.json", "routes.json", "viewports.json"):
            self.assertFalse((webapp / "contracts" / name).exists())
            self.assertTrue((foundation / "contracts" / name).is_file())
        descriptor = json.loads((ROOT / "components" / "foundation.web" / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["component_role"], "foundation")

if __name__ == "__main__":
    unittest.main()
