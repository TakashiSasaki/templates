import json
from pathlib import Path
import unittest


class PublicationAutomationContractTests(unittest.TestCase):
    def test_default_is_shadow_and_self_update_is_forbidden(self):
        root = Path(__file__).resolve().parents[1]
        value = json.loads((root / "release/publication-automation.json").read_text())
        self.assertEqual(value["mode"], "shadow")
        self.assertFalse(value["self_update"])
        self.assertTrue(all("generated" not in item for item in value["allowed_mutations"]))


if __name__ == "__main__":
    unittest.main()
