from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
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
SPEC = importlib.util.spec_from_file_location("implementation_evidence_readiness", VALIDATOR)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def complete_document() -> dict:
    return {
        "schemaVersion": 2,
        "mode": "product",
        "requirements": [
            {
                "id": "REQ-BROWSER-FILTER",
                "description": "The browser can filter the list.",
                "recordIds": ["browser-filter"],
            }
        ],
        "commands": [
            {
                "id": "browser-tests",
                "command": "python tests/run_browser_tests.py",
                "purpose": "Execute the browser interaction proof.",
            }
        ],
        "releaseGates": [
            {
                "id": "product-release",
                "purpose": "Require executable product evidence before release.",
                "commandIds": ["browser-tests"],
            }
        ],
        "records": [
            {
                "id": "browser-filter",
                "target": {
                    "kind": "contract-item",
                    "contractId": "viewports",
                    "itemKind": "input-capability",
                    "itemId": "filter-control",
                },
                "implementationBoundary": {
                    "status": "verified",
                    "description": "Browser filter implementation exists.",
                    "locator": "src/browser.js",
                },
                "positiveEvidence": [
                    {
                        "id": "browser-filter-positive",
                        "status": "verified",
                        "kind": "end-to-end-test",
                        "executionClass": "browser-interaction",
                        "description": "Filtering changes the visible records.",
                        "locator": "tests/browser/filter.py",
                        "commandId": "browser-tests",
                        "expectedResult": "Only matching records remain visible.",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "browser-filter-negative",
                        "status": "verified",
                        "kind": "end-to-end-test",
                        "executionClass": "browser-interaction",
                        "description": "A non-matching filter hides records.",
                        "locator": "tests/browser/filter.py",
                        "commandId": "browser-tests",
                        "expectedResult": "Non-matching records are not visible.",
                    }
                ],
                "releaseGateIds": ["product-release"],
            }
        ],
    }


class ImplementationEvidenceReadinessTests(unittest.TestCase):
    def test_complete_graph_is_release_ready(self) -> None:
        self.assertEqual(validator.release_readiness_errors(complete_document()), [])

    def test_required_browser_proof_is_incomplete_not_passed(self) -> None:
        value = complete_document()
        value["records"][0]["positiveEvidence"][0] = {
            "id": "browser-filter-positive",
            "status": "required",
            "kind": "end-to-end-test",
            "executionClass": "browser-interaction",
            "description": "Browser interaction still needs to run.",
        }

        errors = validator.release_readiness_errors(value)

        self.assertTrue(
            any("browser-filter-positive" in error and "required" in error for error in errors),
            errors,
        )

    def test_deferred_browser_proof_reports_environment_reason_and_blocks_release(self) -> None:
        value = complete_document()
        value["records"][0]["positiveEvidence"][0] = {
            "id": "browser-filter-positive",
            "status": "deferred",
            "kind": "end-to-end-test",
            "executionClass": "browser-interaction",
            "description": "Browser interaction could not execute here.",
            "deferredReason": "Browser runtime cannot reach the local service.",
        }

        self.assertEqual(validator.requirement_traceability_errors(value), [])
        errors = validator.release_readiness_errors(value)

        self.assertTrue(
            any("deferred" in error and "cannot reach" in error for error in errors),
            errors,
        )

    def test_static_substitute_does_not_clear_deferred_browser_requirement(self) -> None:
        value = complete_document()
        record = value["records"][0]
        record["positiveEvidence"] = [
            {
                "id": "static-control-inspection",
                "status": "verified",
                "kind": "inspection",
                "executionClass": "static-inspection",
                "description": "HTML contains the expected severity control.",
                "locator": "tests/test_markup.py",
                "commandId": "browser-tests",
                "expectedResult": "The expected control exists in markup.",
            },
            {
                "id": "browser-filter-positive",
                "status": "deferred",
                "kind": "end-to-end-test",
                "executionClass": "browser-interaction",
                "description": "Real browser filtering remains unverified.",
                "deferredReason": "No usable browser runtime is available.",
            },
        ]

        errors = validator.release_readiness_errors(value)

        self.assertTrue(any("browser-filter-positive" in error for error in errors), errors)
        self.assertFalse(any("static-control-inspection" in error for error in errors), errors)

    def test_missing_requirement_ledger_cannot_be_release_ready(self) -> None:
        value = complete_document()
        value["requirements"] = []

        errors = validator.release_readiness_errors(value)

        self.assertIn(
            "release readiness requires at least one explicit product requirement",
            errors,
        )

    def test_unverified_boundary_blocks_release_without_destroying_structure(self) -> None:
        value = copy.deepcopy(complete_document())
        value["records"][0]["implementationBoundary"] = {
            "status": "required",
            "description": "Implementation still needs to be completed.",
        }

        errors = validator.release_readiness_errors(value)

        self.assertIn(
            "record browser-filter: implementation boundary is not verified",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
