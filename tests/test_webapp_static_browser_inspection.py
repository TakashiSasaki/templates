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
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / "schemas"
    / "implementation-evidence.schema.json"
)
VALIDATOR_PATH = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_implementation_evidence.py"
)
COMMON_DIR = (
    ROOT
    / "components"
    / "lifecycle.contract-evolution"
    / "files"
    / ".template-composition"
    / "validators"
)
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SPEC = importlib.util.spec_from_file_location("static_browser_inspection_validator", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def evidence(proof_kind: str = "inspection", proof_status: str = "verified") -> dict:
    value = {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 5,
        "mode": "product",
        "commands": [{
            "id": "browser-proof",
            "command": "python tests/browser_proof.py",
            "purpose": "Run the browser proof.",
        }],
        "releaseGates": [{
            "id": "release",
            "purpose": "Require the browser proof.",
            "commandIds": ["browser-proof"],
        }],
        "requirements": [{
            "id": "REQ-BROWSER-CONTROLS",
            "description": "The browser page exposes working filter controls.",
            "recordIds": ["home"],
            "requiredPositiveProofKinds": ["end-to-end-test", "accessibility-test"],
        }],
        "records": [{
            "id": "home",
            "target": {
                "kind": "contract-item",
                "contractId": "routes",
                "itemKind": "route",
                "itemId": "home",
            },
            "implementationBoundary": {
                "status": "verified",
                "description": "Static HTML contains controls, viewport meta, and responsive CSS.",
                "locator": "static/index.html",
            },
            "positiveEvidence": [{
                "id": "controls-positive",
                "status": proof_status,
                "kind": proof_kind,
                "description": "HTML parser finds the controls, viewport meta tag, and CSS media query.",
                "locator": "tests/test_static_html.py",
                "commandId": "browser-proof",
                "expectedResult": "The expected static markup and responsive declarations are present.",
            }],
            "negativeEvidence": [{
                "id": "controls-negative",
                "status": proof_status,
                "kind": proof_kind,
                "description": "HTML parser finds no static invalid-filter handling.",
                "locator": "tests/test_static_html.py",
                "commandId": "browser-proof",
                "expectedResult": "Static inspection does not claim interactive behavior.",
            }],
            "releaseGateIds": ["release"],
        }],
    }
    browser_ids = (
        {"browser-proof"}
        if proof_kind in {"end-to-end-test", "accessibility-test"}
        else set()
    )
    return upgrade_product_evidence_v6(
        value,
        browser_command_ids=browser_ids,
        harness_by_command={"browser-proof": "tests/browser_proof.py"},
    )


class StaticBrowserInspectionTests(unittest.TestCase):
    def write_fixture(self, root: Path, value: dict) -> None:
        contracts = root / "contracts"
        contracts.mkdir(parents=True)
        (contracts / "manifest.json").write_text(
            json.dumps({
                "contracts": [{
                    "id": "routes",
                    "versionHistory": [{"version": 1}],
                }]
            }),
            encoding="utf-8",
        )
        (contracts / "implementation-evidence.json").write_text(
            json.dumps(value), encoding="utf-8"
        )
        materialize_declared_harnesses(root, value)

    def test_static_inspection_is_schema_valid_but_not_browser_complete(self) -> None:
        value = evidence()
        Draft202012Validator(
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        ).validate(value)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            structural_errors = validator.validate(root)
            release_blockers = validator.release_readiness_errors(value)
        self.assertTrue(
            any("required kind" in error for error in structural_errors),
            structural_errors,
        )
        self.assertTrue(
            any("required kind" in error for error in release_blockers),
            release_blockers,
        )

    def test_real_browser_proof_closes_the_static_inspection_gap(self) -> None:
        value = evidence("end-to-end-test")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])
        self.assertEqual(validator.release_readiness_errors(value), [])

    def test_browser_unavailable_is_deferred_and_not_release_ready(self) -> None:
        value = evidence("end-to-end-test", "deferred")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])
        blockers = validator.release_readiness_errors(value)
        self.assertTrue(any("deferred" in blocker for blocker in blockers), blockers)


if __name__ == "__main__":
    unittest.main()
