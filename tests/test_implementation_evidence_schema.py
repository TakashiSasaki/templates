from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / "schemas"
    / "implementation-evidence.schema.json"
)


def load_schema() -> dict:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("implementation-evidence schema must be an object")
    return value


def product_document() -> dict:
    return {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 1,
        "mode": "product",
        "commands": [
            {
                "id": "product-proof",
                "command": "python product/prove.py",
                "purpose": "Prove the product contract implementation.",
            }
        ],
        "releaseGates": [
            {
                "id": "product-release",
                "purpose": "Block release until the product proof passes.",
                "commandIds": ["product-proof"],
            }
        ],
        "records": [
            {
                "id": "demo-record",
                "target": {
                    "kind": "contract-item",
                    "contractId": "demo_contract",
                    "itemKind": "demo-item",
                    "itemId": "demo",
                },
                "implementationBoundary": {
                    "status": "verified",
                    "description": "The demo implementation boundary is verified.",
                    "locator": "product/demo.py",
                },
                "positiveEvidence": [
                    {
                        "id": "demo-positive",
                        "status": "verified",
                        "kind": "integration-test",
                        "description": "The positive product path is verified.",
                        "locator": "tests/test_demo.py",
                        "commandId": "product-proof",
                        "expectedResult": "The positive product path passes.",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "demo-negative",
                        "status": "verified",
                        "kind": "integration-test",
                        "description": "The negative product path is verified.",
                        "locator": "tests/test_demo.py",
                        "commandId": "product-proof",
                        "expectedResult": "Invalid product state is rejected.",
                    }
                ],
                "releaseGateIds": ["product-release"],
            }
        ],
    }


class ImplementationEvidenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_schema()
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def assert_valid(self, value: dict) -> None:
        self.validator.validate(value)

    def assert_invalid(self, value: dict) -> None:
        with self.assertRaises(ValidationError):
            self.validator.validate(value)

    def test_complete_product_evidence_is_schema_valid(self) -> None:
        self.assert_valid(product_document())

    def test_product_boundary_requires_verified_status_and_locator(self) -> None:
        missing_locator = product_document()
        del missing_locator["records"][0]["implementationBoundary"]["locator"]
        self.assert_invalid(missing_locator)

        unverified = product_document()
        unverified["records"][0]["implementationBoundary"]["status"] = "required"
        self.assert_invalid(unverified)

    def test_product_proofs_require_complete_verified_metadata(self) -> None:
        for evidence_key in ("positiveEvidence", "negativeEvidence"):
            for field in ("kind", "locator", "commandId", "expectedResult"):
                value = product_document()
                del value["records"][0][evidence_key][0][field]
                with self.subTest(evidence_key=evidence_key, field=field):
                    self.assert_invalid(value)

            value = product_document()
            value["records"][0][evidence_key][0]["status"] = "required"
            with self.subTest(evidence_key=evidence_key, field="status"):
                self.assert_invalid(value)

    def test_product_record_requires_at_least_one_release_gate(self) -> None:
        value = product_document()
        value["records"][0]["releaseGateIds"] = []
        self.assert_invalid(value)

    def test_template_mode_remains_structurally_empty(self) -> None:
        value = {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 1,
            "mode": "template",
            "commands": [],
            "releaseGates": [],
            "records": [],
        }
        self.assert_valid(value)

        nonempty = copy.deepcopy(value)
        nonempty["commands"] = product_document()["commands"]
        self.assert_invalid(nonempty)


if __name__ == "__main__":
    unittest.main()
