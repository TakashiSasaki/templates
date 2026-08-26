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


class WebappWorklistProofStatusTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

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
                        "id": "REQ-ROUTE-FOCUS",
                        "description": "Route entry honors the declared focus target.",
                        "recordIds": ["routes-route-home"],
                        "requiredPositiveProofKinds": [requirement_kind],
                    }
                ],
                "records": [
                    {
                        "id": "routes-route-home",
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
                    }
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
            self.assertEqual(
                worklist["recordStatuses"],
                [{"id": "routes-route-home", "status": "missing"}],
            )
            self.assertEqual(worklist["statusCounts"]["missing"], 1)
            self.assertEqual(worklist["requirements"][0]["status"], "missing")
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
            self.assertEqual(
                worklist["artifactProofRequirements"],
                [
                    {
                        "recordId": "routes-route-home",
                        "target": {
                            "kind": "contract-item",
                            "contractId": "routes",
                            "itemKind": "route",
                            "itemId": "home",
                        },
                        "positiveEvidenceKindAtLeastOneOf": [
                            "accessibility-test",
                            "end-to-end-test",
                        ],
                        "negativeEvidenceKindAtLeastOneOf": [
                            "accessibility-test",
                            "end-to-end-test",
                        ],
                        "linkedRequirementRequiredPositiveProofKindAtLeastOneOf": [
                            "accessibility-test",
                            "end-to-end-test",
                        ],
                    }
                ],
            )

    def test_strong_record_does_not_hide_weak_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="end-to-end-test",
                requirement_kind="integration-test",
            )

            self.assertEqual(worklist["recordStatuses"][0]["status"], "verified")
            self.assertEqual(worklist["statusCounts"]["verified"], 1)
            self.assertEqual(worklist["requirements"][0]["status"], "missing")
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
            self.assertEqual(worklist["status"], "missing")

    def test_browser_strength_projects_verified_only_when_both_layers_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="end-to-end-test",
                requirement_kind="end-to-end-test",
            )

            self.assertEqual(worklist["recordStatuses"][0]["status"], "verified")
            self.assertEqual(worklist["requirements"][0]["status"], "verified")
            self.assertEqual(worklist["statusCounts"]["verified"], 1)
            self.assertEqual(worklist["requirementStatusCounts"]["verified"], 1)
            self.assertEqual(worklist["status"], "verified")

    def test_deferred_browser_proof_remains_release_blocking_in_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            worklist = self.render(
                Path(temp_dir),
                proof_kind="accessibility-test",
                requirement_kind="accessibility-test",
                proof_status="deferred",
            )

            self.assertEqual(worklist["recordStatuses"][0]["status"], "deferred")
            self.assertEqual(worklist["requirements"][0]["status"], "deferred")
            self.assertEqual(worklist["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
