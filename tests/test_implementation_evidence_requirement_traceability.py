from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT / "components" / "lifecycle.implementation-evidence" / "files"
    / "schemas" / "implementation-evidence.schema.json"
)
VALIDATOR_PATH = (
    ROOT / "components" / "lifecycle.implementation-evidence" / "files"
    / ".template-composition" / "validators" / "validate_implementation_evidence.py"
)
COMMON_DIR = (
    ROOT / "components" / "lifecycle.contract-evolution" / "files"
    / ".template-composition" / "validators"
)
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SPEC = importlib.util.spec_from_file_location(
    "implementation_evidence_requirement_validator", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def requirement(record_id: str = "browser-filter") -> dict:
    return {
        "id": "REQ-SEVERITY-BROWSER-FILTER",
        "description": "Browser UI can filter records by severity.",
        "recordIds": [record_id],
        "requiredPositiveProofKinds": ["end-to-end-test"],
    }


def evidence(*, requirements: list[dict] | None = None, positive_status: str = "verified") -> dict:
    record = {
        "id": "browser-filter",
        "target": {
            "kind": "contract-item",
            "contractId": "surfaces",
            "itemKind": "surface",
            "itemId": "main",
        },
        "implementationBoundary": {
            "status": "verified",
            "description": "The browser filter implementation boundary is identified.",
            "locator": "app.py",
        },
        "positiveEvidence": [{
            "id": "browser-filter-positive",
            "status": positive_status,
            "kind": "end-to-end-test",
            "description": "The browser filter is exercised.",
            "locator": "tests/test_browser_filter.py",
            "commandId": "product-proof",
            "expectedResult": "Filtering changes the visible records.",
        }],
        "negativeEvidence": [{
            "id": "browser-filter-negative",
            "status": "verified",
            "kind": "end-to-end-test",
            "description": "An invalid filter is rejected.",
            "locator": "tests/test_browser_filter.py",
            "commandId": "product-proof",
            "expectedResult": "Invalid filter input is rejected.",
        }],
        "releaseGateIds": ["product-release"],
    }
    result = {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 3,
        "mode": "product",
        "commands": [{
            "id": "product-proof",
            "command": "python tests/test_browser_filter.py",
            "purpose": "Run the product evidence proof.",
        }],
        "releaseGates": [{
            "id": "product-release",
            "purpose": "Block release until product evidence passes.",
            "commandIds": ["product-proof"],
        }],
        "records": [record],
    }
    if requirements is not None:
        result["requirements"] = requirements
    return result


class ImplementationEvidenceRequirementTraceabilityTests(unittest.TestCase):
    def write_fixture(self, root: Path, value: dict) -> None:
        contracts = root / "contracts"
        contracts.mkdir(parents=True)
        (contracts / "manifest.json").write_text(json.dumps({
            "contracts": [{
                "id": "surfaces",
                "versionHistory": [{"version": 1}],
            }]
        }), encoding="utf-8")
        (contracts / "implementation-evidence.json").write_text(
            json.dumps(value), encoding="utf-8"
        )

    def test_closed_requirement_graph_is_accepted(self) -> None:
        value = evidence(requirements=[requirement()])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])

    def test_product_without_requirement_ledger_is_rejected_semantically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, evidence())
            errors = validator.validate(root)
            self.assertTrue(
                any("requires a non-empty requirements ledger" in error for error in errors),
                errors,
            )
            readiness = validator.release_readiness_errors(evidence())
            self.assertTrue(
                any("requires a non-empty requirements ledger" in error for error in readiness),
                readiness,
            )

    def test_product_with_empty_requirement_ledger_is_rejected_semantically(self) -> None:
        value = evidence(requirements=[])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
            self.assertTrue(
                any("requires a non-empty requirements ledger" in error for error in errors),
                errors,
            )

    def test_requirement_with_missing_record_is_rejected(self) -> None:
        value = evidence(requirements=[requirement("missing-browser-filter")])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
            self.assertTrue(
                any("unknown implementation-evidence record" in error for error in errors),
                errors,
            )

    def test_requirement_cannot_be_satisfied_by_unverified_positive_proof(self) -> None:
        value = evidence(
            requirements=[requirement()],
            positive_status="required",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
            self.assertTrue(
                any("no traceable positive evidence" in error for error in errors),
                errors,
            )

    def test_schema_declares_requirement_shape_and_rejects_empty_fields(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        schema_validator = Draft202012Validator(schema)
        value = evidence(requirements=[requirement()])
        schema_validator.validate(value)

        invalid_records = json.loads(json.dumps(value))
        invalid_records["requirements"][0]["recordIds"] = []
        with self.assertRaises(ValidationError):
            schema_validator.validate(invalid_records)

        missing_kinds = json.loads(json.dumps(value))
        del missing_kinds["requirements"][0]["requiredPositiveProofKinds"]
        with self.assertRaises(ValidationError):
            schema_validator.validate(missing_kinds)


if __name__ == "__main__":
    unittest.main()
