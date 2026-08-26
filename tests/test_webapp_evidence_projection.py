from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_PATH = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
    / "scaffold_webapp_evidence.py"
)
TARGET_SCRIPTS = SCAFFOLD_PATH.parent
if str(TARGET_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TARGET_SCRIPTS))
SPEC = importlib.util.spec_from_file_location("scaffold_webapp_evidence_projection", SCAFFOLD_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Webapp evidence scaffold")
scaffold = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scaffold)


class WebappEvidenceProjectionTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def fixture(self, root: Path, proof_status: str = "verified") -> Path:
        self.write_json(root / "contracts/surfaces.json", {"surfaces": [{"id": "main"}]})
        self.write_json(root / "contracts/routes.json", {"routes": []})
        self.write_json(root / "contracts/ui-states.json", {"states": []})
        self.write_json(
            root / "contracts/viewports.json",
            {"viewports": [], "inputCapabilities": []},
        )
        self.write_json(
            root / "contracts/implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 3,
                "mode": "product",
                "commands": [],
                "releaseGates": [],
                "requirements": [
                    {
                        "id": "REQ-MAIN-BROWSER",
                        "description": "The main browser surface is usable.",
                        "recordIds": ["surfaces-surface-main"],
                        "requiredPositiveProofKinds": ["end-to-end-test"],
                    }
                ],
                "records": [
                    {
                        "id": "surfaces-surface-main",
                        "target": {
                            "kind": "contract-item",
                            "contractId": "surfaces",
                            "itemKind": "surface",
                            "itemId": "main",
                        },
                        "implementationBoundary": {"status": "verified"},
                        "positiveEvidence": [
                            {"status": proof_status, "kind": "end-to-end-test"}
                        ],
                        "negativeEvidence": [
                            {"status": "verified", "kind": "end-to-end-test"}
                        ],
                        "releaseGateIds": ["release"],
                    }
                ],
            },
        )
        return root

    def assert_render_does_not_mutate(self, root: Path) -> dict:
        canonical = root / "contracts/implementation-evidence.json"
        before = canonical.read_bytes()
        worklist = scaffold.render_worklist(root)
        self.assertEqual(canonical.read_bytes(), before)
        return worklist

    def test_projection_is_verified_deferred_or_missing_without_mutating_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.fixture(root)
            verified = self.assert_render_does_not_mutate(root)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["statusCounts"]["verified"], 1)
            self.assertEqual(
                verified["recordStatuses"],
                [{"id": "surfaces-surface-main", "status": "verified"}],
            )
            self.assertEqual(verified["requirements"][0]["status"], "verified")
            self.assertEqual(verified["artifactProofRequirements"], [])

            self.fixture(root, "deferred")
            deferred = self.assert_render_does_not_mutate(root)
            self.assertEqual(deferred["status"], "deferred")
            self.assertEqual(deferred["requirements"][0]["status"], "deferred")
            self.assertEqual(deferred["recordStatuses"][0]["status"], "deferred")

            self.fixture(root, "required")
            missing = self.assert_render_does_not_mutate(root)
            self.assertEqual(missing["status"], "missing")
            self.assertEqual(missing["requirements"][0]["status"], "missing")
            self.assertEqual(missing["recordStatuses"][0]["status"], "missing")

    def test_missing_canonical_evidence_is_a_missing_worklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_json(root / "contracts/surfaces.json", {"surfaces": [{"id": "main"}]})
            self.write_json(root / "contracts/routes.json", {"routes": [{"id": "home"}]})
            self.write_json(root / "contracts/ui-states.json", {"states": []})
            self.write_json(
                root / "contracts/viewports.json",
                {"viewports": [{"id": "base"}], "inputCapabilities": ["keyboard"]},
            )

            worklist = scaffold.render_worklist(root)

            self.assertEqual(worklist["status"], "missing")
            self.assertEqual(worklist["statusCounts"]["missing"], 4)
            self.assertTrue(
                all(item["status"] == "missing" for item in worklist["recordStatuses"])
            )
            self.assertEqual(worklist["requirements"], [])
            self.assertEqual(
                [item["recordId"] for item in worklist["artifactProofRequirements"]],
                [
                    "routes-route-home",
                    "viewports-input-capability-keyboard",
                    "viewports-viewport-base",
                ],
            )
            for item in worklist["artifactProofRequirements"]:
                self.assertEqual(
                    item["positiveEvidenceKindAtLeastOneOf"],
                    ["accessibility-test", "end-to-end-test"],
                )
                self.assertEqual(
                    item["negativeEvidenceKindAtLeastOneOf"],
                    ["accessibility-test", "end-to-end-test"],
                )
                self.assertEqual(
                    item["linkedRequirementRequiredPositiveProofKindAtLeastOneOf"],
                    ["accessibility-test", "end-to-end-test"],
                )


if __name__ == "__main__":
    unittest.main()
