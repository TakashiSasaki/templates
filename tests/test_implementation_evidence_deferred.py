from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

from jsonschema import Draft202012Validator

from executable_proof_test_support import (
    materialize_declared_harnesses,
    upgrade_product_evidence_v6,
)

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
    "implementation_evidence_deferred_validator", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def product_evidence(status: str = "verified") -> dict:
    value = {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 5,
        "mode": "product",
        "commands": [{
            "id": "browser-proof",
            "command": "python tests/browser_proof.py",
            "purpose": "Exercise the browser interaction proof.",
        }],
        "releaseGates": [{
            "id": "release",
            "purpose": "Run all product release proofs.",
            "commandIds": ["browser-proof"],
        }],
        "requirements": [{
            "id": "browser-filter",
            "description": "Browser UI can filter records.",
            "recordIds": ["browser-filter"],
            "requiredPositiveProofKinds": ["end-to-end-test"],
        }],
        "records": [{
            "id": "browser-filter",
            "target": {
                "kind": "contract-item",
                "contractId": "surfaces",
                "itemKind": "surface",
                "itemId": "main",
            },
            "implementationBoundary": {
                "status": "verified",
                "description": "The browser filter boundary is implemented.",
                "locator": "app.py",
            },
            "positiveEvidence": [{
                "id": "browser-filter-positive",
                "status": status,
                "kind": "end-to-end-test",
                "description": "The browser filter changes visible records.",
                "locator": "tests/browser_proof.py",
                "commandId": "browser-proof",
                "expectedResult": "Filtered records are visible.",
            }],
            "negativeEvidence": [{
                "id": "browser-filter-negative",
                "status": "verified",
                "kind": "end-to-end-test",
                "description": "Invalid filtering is rejected.",
                "locator": "tests/browser_proof.py",
                "commandId": "browser-proof",
                "expectedResult": "Invalid filter is rejected.",
            }],
            "releaseGateIds": ["release"],
        }],
    }
    return upgrade_product_evidence_v6(
        value,
        browser_command_ids={"browser-proof"},
    )


class DeferredImplementationEvidenceTests(unittest.TestCase):
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

    def test_deferred_product_proof_is_structurally_valid(self) -> None:
        value = product_evidence("deferred")
        Draft202012Validator(
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        ).validate(value)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])

    def test_deferred_product_proof_blocks_release_readiness(self) -> None:
        value = product_evidence("deferred")
        blockers = validator.release_readiness_errors(value)
        self.assertTrue(
            any(
                "browser-filter-positive" in blocker
                and "deferred" in blocker
                for blocker in blockers
            ),
            blockers,
        )

    def test_verified_product_proof_passes_release_readiness(self) -> None:
        self.assertEqual(validator.release_readiness_errors(product_evidence()), [])


if __name__ == "__main__":
    unittest.main()
