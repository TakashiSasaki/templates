from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
    / "validate_webapp_evidence.py"
)
TARGETS_DIR = VALIDATOR_PATH.parent
if str(TARGETS_DIR) not in sys.path:
    sys.path.insert(0, str(TARGETS_DIR))
SPEC = importlib.util.spec_from_file_location(
    "webapp_focus_target_evidence_validator", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Webapp evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def evidence(
    *,
    contract_id: str = "routes",
    item_kind: str = "route",
    proof_kind: str = "integration-test",
    required_kind: str = "integration-test",
) -> dict:
    return {
        "mode": "product",
        "commands": [
            {
                "id": "focus-proof",
                "execution": {
                    "capabilities": [
                        "integration",
                        "end-to-end",
                        "accessibility",
                        "browser",
                    ]
                },
            }
        ],
        "releaseGates": [],
        "requirements": [
            {
                "id": "REQ-FOCUS-TARGET",
                "description": "The declared browser route focus target is honored.",
                "recordIds": ["focus-target"],
                "requiredPositiveProofKinds": [required_kind],
            }
        ],
        "records": [
            {
                "id": "focus-target",
                "target": {
                    "kind": "contract-item",
                    "contractId": contract_id,
                    "itemKind": item_kind,
                    "itemId": "home",
                },
                "implementationBoundary": {"status": "verified"},
                "positiveEvidence": [
                    {
                        "id": "positive",
                        "status": "verified",
                        "kind": proof_kind,
                        "commandId": "focus-proof",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "negative",
                        "status": "verified",
                        "kind": proof_kind,
                        "commandId": "focus-proof",
                    }
                ],
                "releaseGateIds": ["release"],
            }
        ],
    }


class WebappFocusTargetEvidenceTests(unittest.TestCase):
    def test_browser_sensitive_target_families_are_explicit_and_narrow(self) -> None:
        self.assertEqual(
            validator.BROWSER_SENSITIVE_CONTRACT_ITEMS,
            {
                ("routes", "route"),
                ("viewports", "input-capability"),
                ("viewports", "viewport"),
            },
        )

    def test_route_target_is_browser_sensitive(self) -> None:
        target = evidence()["records"][0]["target"]
        self.assertTrue(validator.requires_browser_level_proof(target))

    def test_integration_only_route_proof_is_rejected(self) -> None:
        value = evidence()
        errors = validator.browser_level_proof_errors(value)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all("browser-level proof kind" in error for error in errors))

    def test_browser_proof_does_not_excuse_weak_requirement_declaration(self) -> None:
        value = evidence(proof_kind="end-to-end-test")
        self.assertEqual(validator.browser_level_proof_errors(value), [])
        errors = validator.browser_level_requirement_errors(value)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("requiredPositiveProofKinds", errors[0])

    def test_browser_proof_and_requirement_declaration_close_focus_gap(self) -> None:
        value = evidence(
            proof_kind="end-to-end-test",
            required_kind="accessibility-test",
        )
        self.assertEqual(validator.browser_level_proof_errors(value), [])
        self.assertEqual(validator.browser_level_requirement_errors(value), [])

    def test_webapp_only_validation_can_omit_generic_requirement_ledger(self) -> None:
        value = evidence(proof_kind="end-to-end-test")
        del value["requirements"]
        self.assertEqual(validator.browser_level_requirement_errors(value), [])

    def test_non_browser_surface_target_keeps_integration_proof(self) -> None:
        value = evidence(contract_id="surfaces", item_kind="surface")
        self.assertEqual(validator.browser_level_proof_errors(value), [])
        self.assertEqual(validator.browser_level_requirement_errors(value), [])


if __name__ == "__main__":
    unittest.main()
