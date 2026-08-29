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


class WebappWorklistProofStatusTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def status_for(self, worklist: dict, record_id: str) -> str:
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

    def render(
        self,
        root: Path,
        *,
        proof_kind: str,
        requirement_kind: str,
        proof_status: str = "verified",
    ) -> dict:
        self.write_json(root / "contracts/surfaces.json", {"surfaces": []})
        self.write_json(root / "contracts/routes.json", {"routes": [{"id": "home"}]})
        self.write_json(root / "contracts/ui-states.json", {"states": []})
        self.write_json(
            root / "contracts/viewports.json",
            {"viewports": [], "inputCapabilities": []},
        )
        self.write_json(
            root / "contracts/implementation-evidence.json",
            {
                "mode": "product",
                "requirements": [
                    {
                        "id": "REQ-BROWSER-IDENTITY",
                        "description": "Browser identity is observable through the browser boundary.",
                        "recordIds": [IDENTITY_RECORD_ID],
                        "requiredPositiveProofKinds": ["end-to-end-test"],
                    },
                    {
                        "id": "REQ-ROUTE-FOCUS",
                        "description": "Route entry honors the declared focus target.",
                        "recordIds": [ROUTE_RECORD_ID],
                        "requiredPositiveProofKinds": [requirement_kind],
                    },
                ],
                "records": [
                    {
                        "id": IDENTITY_RECORD_ID,
                        "target": {
                            "kind": "contract-item",
                            "contractId": "browser_identity",
                            "itemKind": "proof-family",
                            "itemId": "browser-identity",
                        },
                        "implementationBoundary": {"status": "verified"},
                        "positiveEvidence": [
                            {"status": "verified", "kind": "end-to-end-test"}
                        ],
                        "negativeEvidence": [
                            {"status": "verified", "kind": "end-to-end-test"}
                        ],
                        "releaseGateIds": ["product-release"],
                    },
                    {
                        "id": ROUTE_RECORD_ID,
                        "target": {
                            "kind": "contract-item",
                            "contractId": "routes",
                            "itemKind": "route",
                            "itemId": "home",
                        },
                        "implementationBoundary": {"status": "verified"},
                        "positiveEvidence": [
                            {"status": proof_status, "kind": proof_kind}
                        ],
                        "negativeEvidence": [
                            {"status": proof_status, "kind": proof_kind}
                        ],
                        "releaseGateIds": ["product-release"],
                    },
                ],
            },
        )
        return scaffold.render_worklist(root)

    def test_weak_browser_record_and_requirement_remain_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="integration-test",
                requirement_kind="integration-test",
            )

            self.assertEqual(worklist["status"], "missing")
            self.assertEqual(self.status_for(worklist, IDENTITY_RECORD_ID), "verified")
            self.assertEqual(self.status_for(worklist, ROUTE_RECORD_ID), "missing")
            self.assertEqual(worklist["statusCounts"]["missing"], 1)
            self.assertEqual(worklist["statusCounts"]["verified"], 1)
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "missing"
            )
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
            self.assertEqual(worklist["requirementStatusCounts"]["verified"], 1)
            proof_requirements = {
                item["recordId"]: item for item in worklist["artifactProofRequirements"]
            }
            self.assertEqual(set(proof_requirements), {IDENTITY_RECORD_ID, ROUTE_RECORD_ID})
            expected_browser_kinds = ["accessibility-test", "end-to-end-test"]
            for item in proof_requirements.values():
                self.assertEqual(
                    item["positiveEvidenceKindAtLeastOneOf"], expected_browser_kinds
                )
                self.assertEqual(
                    item["negativeEvidenceKindAtLeastOneOf"], expected_browser_kinds
                )
                self.assertEqual(
                    item["linkedRequirementRequiredPositiveProofKindAtLeastOneOf"],
                    expected_browser_kinds,
                )

    def test_strong_record_does_not_hide_weak_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="end-to-end-test",
                requirement_kind="integration-test",
            )

            self.assertEqual(self.status_for(worklist, ROUTE_RECORD_ID), "verified")
            self.assertEqual(worklist["statusCounts"]["verified"], 2)
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "missing"
            )
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
            self.assertEqual(worklist["requirementStatusCounts"]["verified"], 1)
            self.assertEqual(worklist["status"], "missing")

    def test_browser_strength_projects_verified_only_when_both_layers_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="end-to-end-test",
                requirement_kind="end-to-end-test",
            )

            self.assertEqual(self.status_for(worklist, ROUTE_RECORD_ID), "verified")
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "verified"
            )
            self.assertEqual(worklist["statusCounts"]["verified"], 2)
            self.assertEqual(worklist["requirementStatusCounts"]["verified"], 2)
            self.assertEqual(worklist["status"], "verified")

    def test_deferred_browser_proof_remains_release_blocking_in_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="accessibility-test",
                requirement_kind="accessibility-test",
                proof_status="deferred",
            )

            self.assertEqual(self.status_for(worklist, ROUTE_RECORD_ID), "deferred")
            self.assertEqual(
                self.requirement_status(worklist, "REQ-ROUTE-FOCUS"), "deferred"
            )
            self.assertEqual(worklist["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
