from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class PlanningConsumerValidationTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_planning_requirement_ledger_is_valid_but_not_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(
                config,
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
            )
            applied = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--config",
                    str(config),
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

            self.write_json(
                target / "contracts" / "implementation-evidence.json",
                {
                    "$schema": "../schemas/implementation-evidence.schema.json",
                    "schemaVersion": 6,
                    "mode": "planning",
                    "commands": [],
                    "releaseGates": [],
                    "records": [],
                    "requirements": [
                        {
                            "id": "REQ-PLAN-ROUTE-FOCUS",
                            "description": "Route entry places focus on the declared focus target.",
                            "targets": [
                                {
                                    "kind": "contract-item",
                                    "contractId": "routes",
                                    "itemKind": "route",
                                    "itemId": "home",
                                }
                            ],
                            "recordIds": [],
                            "requiredPositiveProofKinds": ["end-to-end-test"],
                        }
                    ],
                },
            )

            runner = target / ".template-composition" / "validate.py"
            validated = subprocess.run(
                [sys.executable, str(runner), str(target), "--format", "json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                validated.returncode, 0, validated.stdout + validated.stderr
            )
            payload = json.loads(validated.stdout)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            self.assertIn(
                "Release readiness: NOT READY",
                checks["implementation-evidence"]["stdout"],
            )
            self.assertEqual(checks["webapp-implementation-coverage"]["status"], "passed")
            self.assertIn(
                "Webapp planning targets and browser proof strength: OK",
                checks["webapp-implementation-coverage"]["stdout"],
            )

    def test_template_evidence_is_semantically_validated_not_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(
                config,
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
            )
            applied = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--config",
                    str(config),
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

            runner = target / ".template-composition" / "validate.py"
            validated = subprocess.run(
                [sys.executable, str(runner), str(target), "--format", "json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                validated.returncode, 0, validated.stdout + validated.stderr
            )
            payload = json.loads(validated.stdout)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(payload["status"], "valid")
            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            self.assertIn(
                "Implementation evidence validation: OK",
                checks["implementation-evidence"]["stdout"],
            )
            self.assertNotIn("deferred", checks["implementation-evidence"]["status"])


if __name__ == "__main__":
    unittest.main()
