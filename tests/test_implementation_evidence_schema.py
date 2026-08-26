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
        "schemaVersion": 2,
        "mode": "product",
        "requirements": [
            {
                "id": "REQ-DEMO",
                "description": "The demo product behavior is implemented and proven.",
                "recordIds": ["demo-record"],
            }
        ],
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
                        "executionClass": "process-integration",
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
                        "executionClass": "process-integration",
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

    def test_product_requires_explicit_requirement_ledger(self) -> None:
        value = product_document()
        value["requirements"] = []
        self.assert_invalid(value)

        value = product_document()
        del value["requirements"]
        self.assert_invalid(value)

    def test_stable_uppercase_requirement_id_is_valid(self) -> None:
        value = product_document()
        value["requirements"][0]["id"] = "REQ-SEVERITY-BROWSER-FILTER"
        self.assert_valid(value)

    def test_required_boundary_is_structurally_valid_but_verified_boundary_needs_locator(self) -> None:
        planned = product_document()
        planned["records"][0]["implementationBoundary"] = {
            "status": "required",
            "description": "Implementation is still required.",
        }
        self.assert_valid(planned)

        missing_locator = product_document()
        del missing_locator["records"][0]["implementationBoundary"]["locator"]
        self.assert_invalid(missing_locator)

    def test_proof_execution_class_is_required(self) -> None:
        value = product_document()
        del value["records"][0]["positiveEvidence"][0]["executionClass"]
        self.assert_invalid(value)

    def test_verified_proofs_require_execution_metadata(self) -> None:
        for evidence_key in ("positiveEvidence", "negativeEvidence"):
            for field in ("locator", "commandId", "expectedResult"):
                value = product_document()
                del value["records"][0][evidence_key][0][field]
                with self.subTest(evidence_key=evidence_key, field=field):
                    self.assert_invalid(value)

    def test_required_proof_can_be_recorded_without_executed_result(self) -> None:
        value = product_document()
        value["records"][0]["positiveEvidence"] = [
            {
                "id": "browser-proof-required",
                "status": "required",
                "kind": "end-to-end-test",
                "executionClass": "browser-interaction",
                "description": "A browser proof still needs to run.",
            }
        ]
        self.assert_valid(value)

    def test_deferred_proof_requires_reason_but_not_fake_execution_metadata(self) -> None:
        value = product_document()
        value["records"][0]["positiveEvidence"] = [
            {
                "id": "browser-proof-deferred",
                "status": "deferred",
                "kind": "end-to-end-test",
                "executionClass": "browser-interaction",
                "description": "The intended browser proof could not run here.",
                "deferredReason": "No browser runtime is available in this environment.",
            }
        ]
        self.assert_valid(value)

        missing_reason = copy.deepcopy(value)
        del missing_reason["records"][0]["positiveEvidence"][0]["deferredReason"]
        self.assert_invalid(missing_reason)

    def test_template_mode_remains_structurally_empty(self) -> None:
        value = {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 2,
            "mode": "template",
            "requirements": [],
            "commands": [],
            "releaseGates": [],
            "records": [],
        }
        self.assert_valid(value)

        product = product_document()
        for key in ("requirements", "commands", "releaseGates", "records"):
            nonempty = copy.deepcopy(value)
            nonempty[key] = product[key]
            with self.subTest(rejected_key=key):
                self.assert_invalid(nonempty)


if __name__ == "__main__":
    unittest.main()
