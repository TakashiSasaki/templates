from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class RouteHistoryBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        documents = validate_contracts.load_contract_documents(ROOT)
        self.route = documents["routes"]["routes"][0]
        self.validator = Draft202012Validator(
            validate_contracts.load_json(ROOT / "schemas/routes.schema.json")
        )

    def is_valid(self, behavior: str) -> bool:
        route = copy.deepcopy(self.route)
        route["historyBehavior"] = behavior
        document = {
            "$schema": "../schemas/routes.schema.json",
            "schemaVersion": 2,
            "routes": [route],
        }
        return self.validator.is_valid(document)

    def test_supported_values(self) -> None:
        self.assertTrue(self.is_valid("push"))
        self.assertTrue(self.is_valid("replace"))

    def test_external_is_rejected(self) -> None:
        self.assertFalse(self.is_valid("external"))


if __name__ == "__main__":
    unittest.main()
