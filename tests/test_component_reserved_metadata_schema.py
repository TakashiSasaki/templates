from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "component.schema.json"
EXAMPLE = ROOT / "examples" / "component.mcp.json"


class ComponentReservedMetadataSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def assert_reserved(self, destination: str, *, generated: bool) -> None:
        value = copy.deepcopy(self.example)
        if generated:
            value["materials"][0] = {
                "destination": destination,
                "ownership": "generated",
                "generator": "contract-manifest-v1",
            }
        else:
            value["materials"][0]["destination"] = destination
        with self.assertRaises(ValidationError):
            self.validator.validate(value)

    def test_copied_material_rejects_all_composer_owned_metadata(self) -> None:
        for destination in (
            ".template-composition/lock.json",
            ".template-composition/transaction.json",
            ".template-composition/staging",
            ".template-composition/staging/abc/material",
        ):
            with self.subTest(destination=destination):
                self.assert_reserved(destination, generated=False)

    def test_generated_material_rejects_all_composer_owned_metadata(self) -> None:
        for destination in (
            ".template-composition/lock.json",
            ".template-composition/transaction.json",
            ".template-composition/staging",
            ".template-composition/staging/abc/material",
        ):
            with self.subTest(destination=destination):
                self.assert_reserved(destination, generated=True)

    def test_nonreserved_composition_metadata_remains_available_to_components(self) -> None:
        value = copy.deepcopy(self.example)
        value["materials"][0]["destination"] = ".template-composition/validators/example.py"
        self.validator.validate(value)


if __name__ == "__main__":
    unittest.main()
