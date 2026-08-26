from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from executable_proof_test_support import (
    materialize_declared_harnesses,
    upgrade_product_evidence_v6,
)

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
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
    "implementation_evidence_required_kind_validator", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def product_evidence(proof_kind: str) -> dict:
    value = {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 5,
        "mode": "product",
        "commands": [{
            "id": "proof",
            "command": "python tests/proof.py",
            "purpose": "Run the product proof.",
        }],
        "releaseGates": [{
            "id": "release",
            "purpose": "Run the release proof.",
            "commandIds": ["proof"],
        }],
        "requirements": [{
            "id": "browser-severity-filter",
            "description": "Browser UI can filter records by severity.",
            "recordIds": ["severity-filter"],
            "requiredPositiveProofKinds": ["end-to-end-test", "accessibility-test"],
        }],
        "records": [{
            "id": "severity-filter",
            "target": {
                "kind": "contract-item",
                "contractId": "surfaces",
                "itemKind": "surface",
                "itemId": "main",
            },
            "implementationBoundary": {
                "status": "verified",
                "description": "The filter boundary is implemented.",
                "locator": "app.py",
            },
            "positiveEvidence": [{
                "id": "severity-positive",
                "status": "verified",
                "kind": proof_kind,
                "description": "The filter changes visible records.",
                "locator": "tests/proof.py",
                "commandId": "proof",
                "expectedResult": "Only the selected records are visible.",
            }],
            "negativeEvidence": [{
                "id": "severity-negative",
                "status": "verified",
                "kind": "end-to-end-test",
                "description": "Invalid filtering is rejected.",
                "locator": "tests/proof.py",
                "commandId": "proof",
                "expectedResult": "Invalid filter is rejected.",
            }],
            "releaseGateIds": ["release"],
        }],
    }
    return upgrade_product_evidence_v6(value, browser_command_ids={"proof"})


class RequiredPositiveProofKindTests(unittest.TestCase):
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
        materialize_declared_harnesses(root, value)

    def test_requirement_cannot_omit_required_proof_kinds(self) -> None:
        value = product_evidence("end-to-end-test")
        del value["requirements"][0]["requiredPositiveProofKinds"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            structural_errors = validator.validate(root)
        readiness_errors = validator.release_readiness_errors(value)
        self.assertTrue(
            any("requiredPositiveProofKinds" in error for error in structural_errors),
            structural_errors,
        )
        self.assertTrue(
            any("requiredPositiveProofKinds" in error for error in readiness_errors),
            readiness_errors,
        )

    def test_static_inspection_cannot_satisfy_browser_requirement(self) -> None:
        value = product_evidence("inspection")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
        self.assertTrue(
            any("required kind" in error for error in errors),
            errors,
        )

    def test_browser_execution_kind_closes_browser_requirement_edge(self) -> None:
        value = product_evidence("end-to-end-test")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])

    def test_cli_requirement_cannot_use_static_inspection(self) -> None:
        value = product_evidence("inspection")
        requirement = value["requirements"][0]
        requirement["id"] = "cli-severity-filter"
        requirement["description"] = "CLI can filter records by severity."
        requirement["requiredPositiveProofKinds"] = ["integration-test"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
        self.assertTrue(
            any("required kind" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
