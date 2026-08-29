from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
    / "validate_webapp_evidence.py"
)


class WebappCrossCapabilityEvidenceBoundaryTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def record(
        self,
        record_id: str,
        target: dict[str, object],
        *,
        proof_kind: str,
    ) -> dict[str, object]:
        return {
            "id": record_id,
            "target": target,
            "implementationBoundary": {"status": "verified"},
            "positiveEvidence": [
                {
                    "status": "verified",
                    "kind": proof_kind,
                    "commandId": "webapp-proof",
                }
            ],
            "negativeEvidence": [
                {
                    "status": "verified",
                    "kind": proof_kind,
                    "commandId": "webapp-proof",
                }
            ],
            "releaseGateIds": ["release"],
        }

    def fixture(self, root: Path) -> dict[str, object]:
        self.write_json(
            root / "contracts/browser-identity.json",
            {"favicon": {"relation": "icon"}},
        )
        self.write_json(root / "contracts/surfaces.json", {"surfaces": [{"id": "main"}]})
        self.write_json(root / "contracts/routes.json", {"routes": [{"id": "home"}]})
        self.write_json(root / "contracts/ui-states.json", {"states": []})
        self.write_json(
            root / "contracts/viewports.json",
            {"viewports": [], "inputCapabilities": []},
        )
        self.write_json(
            root / "contracts/manifest.json",
            {
                "contracts": [
                    {"id": "browser_identity", "versionHistory": [{"version": 1}]},
                    {"id": "routes", "versionHistory": [{"version": 1}]},
                    {"id": "surfaces", "versionHistory": [{"version": 1}]},
                    {"id": "ui_states", "versionHistory": [{"version": 1}]},
                    {"id": "viewports", "versionHistory": [{"version": 1}]},
                    {"id": "cli_interface", "versionHistory": [{"version": 1}]},
                ]
            },
        )

        evidence = {
            "mode": "product",
            "commands": [
                {
                    "id": "webapp-proof",
                    "execution": {
                        "capabilities": ["integration", "end-to-end", "browser"],
                    },
                }
            ],
            "requirements": [
                {
                    "id": "REQ-FAVICON",
                    "description": "Browser identity declares a favicon.",
                    "recordIds": ["browser-identity-favicon-favicon"],
                    "requiredPositiveProofKinds": ["integration-test"],
                },
                {
                    "id": "REQ-SURFACE",
                    "description": "Main surface exists.",
                    "recordIds": ["surfaces-surface-main"],
                    "requiredPositiveProofKinds": ["integration-test"],
                },
                {
                    "id": "REQ-ROUTE",
                    "description": "Home route works in a browser.",
                    "recordIds": ["routes-route-home"],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                },
                {
                    "id": "REQ-CLI",
                    "description": "CLI entrypoint executes.",
                    "recordIds": ["cli-interface-entrypoint-main"],
                    "requiredPositiveProofKinds": ["integration-test"],
                },
            ],
            "records": [
                self.record(
                    "browser-identity-favicon-favicon",
                    {
                        "kind": "contract-item",
                        "contractId": "browser_identity",
                        "itemKind": "favicon",
                        "itemId": "favicon",
                    },
                    proof_kind="integration-test",
                ),
                self.record(
                    "surfaces-surface-main",
                    {
                        "kind": "contract-item",
                        "contractId": "surfaces",
                        "itemKind": "surface",
                        "itemId": "main",
                    },
                    proof_kind="integration-test",
                ),
                self.record(
                    "routes-route-home",
                    {
                        "kind": "contract-item",
                        "contractId": "routes",
                        "itemKind": "route",
                        "itemId": "home",
                    },
                    proof_kind="end-to-end-test",
                ),
                self.record(
                    "cli-interface-entrypoint-main",
                    {
                        "kind": "contract-item",
                        "contractId": "cli_interface",
                        "itemKind": "entrypoint",
                        "itemId": "main",
                    },
                    proof_kind="integration-test",
                ),
            ],
        }
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return evidence

    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_registered_non_webapp_target_is_left_to_its_owning_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Webapp evidence coverage and proof strength: OK", result.stdout)

    def test_unknown_webapp_owned_target_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = self.fixture(root)
            mutated = deepcopy(evidence)
            mutated["records"].append(
                self.record(
                    "routes-route-missing",
                    {
                        "kind": "contract-item",
                        "contractId": "routes",
                        "itemKind": "route",
                        "itemId": "missing",
                    },
                    proof_kind="end-to-end-test",
                )
            )
            self.write_json(root / "contracts/implementation-evidence.json", mutated)
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("unknown Webapp implementation-evidence target", result.stderr)
            self.assertIn("missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
