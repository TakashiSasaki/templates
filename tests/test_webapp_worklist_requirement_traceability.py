from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
TARGET_SCRIPTS = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
)
if str(TARGET_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TARGET_SCRIPTS))

import scaffold_webapp_evidence as scaffold


IDENTITY_RECORD_ID = "browser-identity-proof-family-browser-identity"
ROUTE_RECORD_ID = "routes-route-home"


class WebappWorklistRequirementTraceabilityTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def write_contracts(self, root: Path) -> None:
        self.write_json(root / "contracts/surfaces.json", {"surfaces": []})
        self.write_json(root / "contracts/routes.json", {"routes": [{"id": "home"}]})
        self.write_json(root / "contracts/ui-states.json", {"states": []})
        self.write_json(
            root / "contracts/viewports.json",
            {"viewports": [], "inputCapabilities": []},
        )

    def strong_browser_identity_record(self) -> dict:
        return {
            "id": IDENTITY_RECORD_ID,
            "target": {
                "kind": "contract-item",
                "contractId": "browser_identity",
                "itemKind": "proof-family",
                "itemId": "browser-identity",
            },
            "implementationBoundary": {"status": "verified"},
            "positiveEvidence": [{"status": "verified", "kind": "end-to-end-test"}],
            "negativeEvidence": [{"status": "verified", "kind": "end-to-end-test"}],
            "releaseGateIds": ["product-release"],
        }

    def strong_route_record(self, *, proof_kind: str = "end-to-end-test") -> dict:
        return {
            "id": ROUTE_RECORD_ID,
            "target": {
                "kind": "contract-item",
                "contractId": "routes",
                "itemKind": "route",
                "itemId": "home",
            },
            "implementationBoundary": {"status": "verified"},
            "positiveEvidence": [{"status": "verified", "kind": proof_kind}],
            "negativeEvidence": [{"status": "verified", "kind": proof_kind}],
            "releaseGateIds": ["product-release"],
        }

    def identity_requirement(self) -> dict:
        return {
            "id": "REQ-BROWSER-IDENTITY",
            "description": "Browser identity is observable at the browser boundary.",
            "recordIds": [IDENTITY_RECORD_ID],
            "requiredPositiveProofKinds": ["end-to-end-test"],
        }

    def record_status(self, worklist: dict, record_id: str) -> str:
        return next(
            item["status"]
            for item in worklist["recordStatuses"]
            if item["id"] == record_id
        )

    def requirement_status(self, worklist: dict, requirement_id: str) -> str:
        return next(
            item["status"]
            for item in worklist["requirements"]
            if item["id"] == requirement_id
        )

    def test_product_with_empty_requirement_ledger_cannot_project_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_contracts(root)
            self.write_json(
                root / "contracts/implementation-evidence.json",
                {
                    "mode": "product",
                    "requirements": [],
                    "records": [
                        self.strong_browser_identity_record(),
                        self.strong_route_record(),
                    ],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(self.record_status(worklist, ROUTE_RECORD_ID), "verified")
            self.assertEqual(self.record_status(worklist, IDENTITY_RECORD_ID), "verified")
            self.assertEqual(worklist["requirements"], [])
            self.assertEqual(worklist["requirementLedgerStatus"], "missing")
            self.assertEqual(worklist["status"], "missing")

    def test_artifact_allowed_declaration_still_requires_matching_positive_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_contracts(root)
            self.write_json(
                root / "contracts/implementation-evidence.json",
                {
                    "mode": "product",
                    "requirements": [
                        self.identity_requirement(),
                        {
                            "id": "REQ-ROUTE-FOCUS",
                            "description": "Route entry honors the declared focus target.",
                            "recordIds": [ROUTE_RECORD_ID],
                            "requiredPositiveProofKinds": ["accessibility-test"],
                        },
                    ],
                    "records": [
                        self.strong_browser_identity_record(),
                        self.strong_route_record(proof_kind="end-to-end-test"),
                    ],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(self.record_status(worklist, ROUTE_RECORD_ID), "verified")
            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "missing"
            )
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
            self.assertEqual(worklist["requirementStatusCounts"]["verified"], 1)
            self.assertEqual(worklist["status"], "missing")

    def test_matching_required_positive_kind_closes_requirement_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_contracts(root)
            self.write_json(
                root / "contracts/implementation-evidence.json",
                {
                    "mode": "product",
                    "requirements": [
                        self.identity_requirement(),
                        {
                            "id": "REQ-ROUTE-FOCUS",
                            "description": "Route entry honors the declared focus target.",
                            "recordIds": [ROUTE_RECORD_ID],
                            "requiredPositiveProofKinds": ["end-to-end-test"],
                        },
                    ],
                    "records": [
                        self.strong_browser_identity_record(),
                        self.strong_route_record(),
                    ],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "verified"
            )
            self.assertEqual(worklist["status"], "verified")


if __name__ == "__main__":
    unittest.main()
