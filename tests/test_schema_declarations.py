from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class SchemaDeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.validators = {
            name: Draft202012Validator(validate_contracts.load_json(ROOT / schema_path))
            for name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items()
        }

    def test_contract_schema_declarations_are_required_and_pinned(self) -> None:
        expected_schema_uris = {
            "surfaces": "../schemas/surfaces.schema.json",
            "routes": "../schemas/routes.schema.json",
            "ui_states": "../schemas/ui-states.schema.json",
            "viewports": "../schemas/viewports.schema.json",
        }

        for contract_name, expected_uri in expected_schema_uris.items():
            with self.subTest(contract=contract_name, case="expected"):
                document = copy.deepcopy(self.documents[contract_name])
                self.assertEqual(expected_uri, document["$schema"])
                self.assertTrue(self.validators[contract_name].is_valid(document))

            with self.subTest(contract=contract_name, case="missing"):
                document = copy.deepcopy(self.documents[contract_name])
                del document["$schema"]
                self.assertFalse(self.validators[contract_name].is_valid(document))

            with self.subTest(contract=contract_name, case="mismatched"):
                document = copy.deepcopy(self.documents[contract_name])
                document["$schema"] = "../schemas/unrelated.schema.json"
                self.assertFalse(self.validators[contract_name].is_valid(document))

    def test_focus_strategies_require_non_whitespace_content(self) -> None:
        original = self.documents["ui_states"]
        for invalid_strategy in (" ", "\n", "\t", " \r\n\t"):
            with self.subTest(focus_strategy=repr(invalid_strategy)):
                document = copy.deepcopy(original)
                document["states"][0]["focusStrategy"] = invalid_strategy
                self.assertFalse(self.validators["ui_states"].is_valid(document))

        document = copy.deepcopy(original)
        document["states"][0]["focusStrategy"] = "  preserve-current-focus  "
        self.assertTrue(self.validators["ui_states"].is_valid(document))


if __name__ == "__main__":
    unittest.main()
