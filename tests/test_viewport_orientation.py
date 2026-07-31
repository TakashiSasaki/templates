from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class ViewportOrientationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema_path = ROOT / "schemas/viewports.schema.json"
        contract_path = ROOT / "contracts/viewports.json"
        cls.validator = Draft202012Validator(
            json.loads(schema_path.read_text(encoding="utf-8"))
        )
        cls.contract = json.loads(contract_path.read_text(encoding="utf-8"))

    def test_repository_contract_requires_orientation_independence(self) -> None:
        self.assertTrue(self.contract["constraints"]["orientationIndependent"])
        self.assertTrue(self.validator.is_valid(self.contract))

    def test_orientation_independence_cannot_be_disabled(self) -> None:
        document = copy.deepcopy(self.contract)
        document["constraints"]["orientationIndependent"] = False
        self.assertFalse(self.validator.is_valid(document))


if __name__ == "__main__":
    unittest.main()
