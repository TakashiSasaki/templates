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

    def strong_route_record(self, *, proof_kind: str = "end-to-end-test") -> dict:
        return {
            "id": "routes-route-home",
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

    def test_product_with_empty_requirement_ledger_cannot_project_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_contracts(root)
            self.write_json(
                root / "contracts/implementation-evidence.json",
                {
                    "mode": "product",
                    "requirements": [],
                    "records": [self.strong_route_record()],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(worklist["recordStatuses"][0]["status"], "verified")
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
                        {
                            "id": "REQ-ROUTE-FOCUS",
                            "description": "Route entry honors the declared focus target.",
                            "recordIds": ["routes-route-home"],
                            "requiredPositiveProofKinds": ["accessibility-test"],
                        }
                    ],
                    "records": [
                        self.strong_route_record(proof_kind="end-to-end-test")
                    ],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(worklist["recordStatuses"][0]["status"], "verified")
            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(worklist["requirements"][0]["status"], "missing")
            self.assertEqual(worklist["requirementStatusCounts"]["missing"], 1)
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
                        {
                            "id": "REQ-ROUTE-FOCUS",
                            "description": "Route entry honors the declared focus target.",
                            "recordIds": ["routes-route-home"],
                            "requiredPositiveProofKinds": ["end-to-end-test"],
                        }
                    ],
                    "records": [self.strong_route_record()],
                },
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(worklist["requirements"][0]["status"], "verified")
            self.assertEqual(worklist["status"], "verified")


if __name__ == "__main__":
    unittest.main()
