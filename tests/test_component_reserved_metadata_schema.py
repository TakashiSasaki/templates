from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_SCHEMA = ROOT / "schemas" / "component.schema.json"
LOCK_SCHEMA = ROOT / "schemas" / "composition-lock.schema.json"
TRANSACTION_SCHEMA = ROOT / "schemas" / "composition-transaction.schema.json"
COMPONENT_EXAMPLE = ROOT / "examples" / "component.mcp.json"
LOCK_EXAMPLE = ROOT / "examples" / "composition-lock.webapp-mcp.json"

RESERVED_DESTINATIONS = (
    ".template-composition",
    ".template-composition/lock.json",
    ".template-composition/lock.json/nested",
    ".template-composition/transaction.json",
    ".template-composition/transaction.json/nested",
    ".template-composition/staging",
    ".template-composition/staging/abc/material",
)
ALLOWED_DESTINATION = ".template-composition/validators/example.py"


class ReservedMetadataSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.component_schema = json.loads(COMPONENT_SCHEMA.read_text(encoding="utf-8"))
        cls.lock_schema = json.loads(LOCK_SCHEMA.read_text(encoding="utf-8"))
        cls.transaction_schema = json.loads(TRANSACTION_SCHEMA.read_text(encoding="utf-8"))
        for schema in (cls.component_schema, cls.lock_schema, cls.transaction_schema):
            Draft202012Validator.check_schema(schema)
        cls.component_validator = Draft202012Validator(cls.component_schema)
        cls.lock_validator = Draft202012Validator(cls.lock_schema)
        cls.transaction_validator = Draft202012Validator(cls.transaction_schema)
        cls.component_example = json.loads(COMPONENT_EXAMPLE.read_text(encoding="utf-8"))
        cls.lock_example = json.loads(LOCK_EXAMPLE.read_text(encoding="utf-8"))

    def component_with_destination(self, destination: str, *, generated: bool) -> dict:
        value = copy.deepcopy(self.component_example)
        if generated:
            value["materials"][0] = {
                "destination": destination,
                "ownership": "generated",
                "generator": "contract-manifest-v1",
            }
        else:
            value["materials"][0]["destination"] = destination
        return value

    def lock_with_destination(self, destination: str) -> dict:
        value = copy.deepcopy(self.lock_example)
        value["files"][0]["destination"] = destination
        return value

    def transaction_with_destination(self, destination: str, *, action: str) -> dict:
        entry = {
            "action": action,
            "destination": destination,
            "component": "capability.example",
            "ownership": "managed",
        }
        if action in {"replace", "remove"}:
            entry["from_sha256"] = "1" * 64
        if action in {"create", "replace"}:
            entry["to_sha256"] = "2" * 64
        return {
            "schema_version": 1,
            "operation": "update",
            "source": {
                "repository": "TakashiSasaki/templates",
                "revision": "a" * 40,
            },
            "old_lock_file_sha256": "3" * 64,
            "new_lock_file_sha256": "4" * 64,
            "old_lock": {},
            "new_lock": {},
            "actions": [entry],
        }

    def test_component_materials_reject_all_reserved_prefixes(self) -> None:
        for generated in (False, True):
            for destination in RESERVED_DESTINATIONS:
                with self.subTest(generated=generated, destination=destination):
                    with self.assertRaises(ValidationError):
                        self.component_validator.validate(
                            self.component_with_destination(destination, generated=generated)
                        )

    def test_lock_inventory_rejects_all_reserved_prefixes(self) -> None:
        for destination in RESERVED_DESTINATIONS:
            with self.subTest(destination=destination):
                with self.assertRaises(ValidationError):
                    self.lock_validator.validate(self.lock_with_destination(destination))

    def test_transaction_actions_reject_all_reserved_prefixes(self) -> None:
        for action in ("create", "replace", "remove"):
            for destination in RESERVED_DESTINATIONS:
                with self.subTest(action=action, destination=destination):
                    with self.assertRaises(ValidationError):
                        self.transaction_validator.validate(
                            self.transaction_with_destination(destination, action=action)
                        )

    def test_nonreserved_composition_metadata_remains_available(self) -> None:
        self.component_validator.validate(
            self.component_with_destination(ALLOWED_DESTINATION, generated=False)
        )
        self.component_validator.validate(
            self.component_with_destination(ALLOWED_DESTINATION, generated=True)
        )
        self.lock_validator.validate(self.lock_with_destination(ALLOWED_DESTINATION))
        for action in ("create", "replace", "remove"):
            with self.subTest(action=action):
                self.transaction_validator.validate(
                    self.transaction_with_destination(ALLOWED_DESTINATION, action=action)
                )


if __name__ == "__main__":
    unittest.main()
