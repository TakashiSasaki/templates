from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class SchemaDeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.validators = {
            name: Draft202012Validator(validate_contracts.load_json(ROOT / schema_path))
            for name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items()
        }

    @staticmethod
    def set_nested(document: Any, path: tuple[str | int, ...], value: Any) -> None:
        target = document
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

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

    def test_schema_dialects_are_pinned_to_draft_2020_12(self) -> None:
        for contract_name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items():
            with self.subTest(contract=contract_name):
                schema = validate_contracts.load_json(ROOT / schema_path)
                self.assertEqual(validate_contracts.SCHEMA_DIALECT, schema["$schema"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
            shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
            schema_path = temporary_root / "schemas/surfaces.schema.json"
            schema = validate_contracts.load_json(schema_path)
            schema["$schema"] = "http://json-schema.org/draft-04/schema#"
            schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
            errors = validate_contracts.validate_repository(temporary_root)

        self.assertTrue(
            any(
                "schemas/surfaces.schema.json: unsupported JSON Schema dialect" in error
                and "draft-04" in error
                for error in errors
            )
        )

    def test_template_schemas_do_not_claim_upstream_repository_identity(self) -> None:
        for contract_name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items():
            with self.subTest(contract=contract_name):
                schema = validate_contracts.load_json(ROOT / schema_path)
                self.assertNotIn("$id", schema)

    def test_required_human_readable_fields_reject_ecmascript_whitespace_only(self) -> None:
        cases = (
            ("surfaces", ("surfaces", 0, "title")),
            ("surfaces", ("surfaces", 0, "purpose")),
            ("routes", ("routes", 0, "accessibility", "focusTarget")),
            ("ui_states", ("states", 0, "description")),
            ("ui_states", ("states", 0, "focusStrategy")),
            ("viewports", ("viewports", 0, "description")),
        )
        invalid_values = (" ", "\n", "\t", " \r\n\t", "\ufeff", " \ufeff\t")

        for contract_name, path in cases:
            for invalid_value in invalid_values:
                with self.subTest(
                    contract=contract_name,
                    path=path,
                    value=repr(invalid_value),
                ):
                    document = copy.deepcopy(self.documents[contract_name])
                    self.set_nested(document, path, invalid_value)
                    self.assertFalse(self.validators[contract_name].is_valid(document))

            with self.subTest(contract=contract_name, path=path, value="padded"):
                document = copy.deepcopy(self.documents[contract_name])
                self.set_nested(document, path, "  meaningful description  ")
                self.assertTrue(self.validators[contract_name].is_valid(document))


if __name__ == "__main__":
    unittest.main()
