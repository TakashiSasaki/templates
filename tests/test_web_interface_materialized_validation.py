from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lifecycle_checkpoint_test_support import (
    create_planning_checkpoint,
    planning_evidence_from_product,
)

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class WebInterfaceMaterializedValidationTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_selected_product_interface_passes_combined_consumer_validation(self) -> None:
        from test_web_interface_contract import WebInterfaceContractTests

        helper = WebInterfaceContractTests()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(
                config,
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {
                        "include": ["capability.web-interface"],
                        "exclude": [],
                    },
                    "parameters": {},
                },
            )
            apply_result = subprocess.run(
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
            self.assertEqual(
                apply_result.returncode,
                0,
                apply_result.stdout + apply_result.stderr,
            )

            product_contract = helper.product_contract()
            product_evidence, planning_evidence = planning_evidence_from_product(
                helper.evidence()
            )
            planning_contract = {
                "$schema": "../schemas/web-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "endpoints": [
                    {
                        "id": endpoint["id"],
                        "kind": endpoint["kind"],
                        "purpose": endpoint["purpose"],
                    }
                    for endpoint in product_contract["endpoints"]
                ],
            }
            self.write_json(
                target / "contracts" / "web-interface.json",
                planning_contract,
            )
            self.write_json(
                target / "contracts" / "implementation-evidence.json",
                planning_evidence,
            )
            create_planning_checkpoint(target)

            self.write_json(
                target / "contracts" / "web-interface.json",
                product_contract,
            )
            self.write_json(
                target / "contracts" / "implementation-evidence.json",
                product_evidence,
            )

            runner = target / ".template-composition" / "validate.py"
            validate_result = subprocess.run(
                [sys.executable, str(runner), str(target), "--format", "json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                payload = json.loads(validate_result.stdout)
            except json.JSONDecodeError as exc:
                self.fail(
                    f"consumer validator did not emit JSON: {exc}\n"
                    f"stdout={validate_result.stdout}\nstderr={validate_result.stderr}"
                )
            self.assertEqual(validate_result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            self.assertEqual(checks["lifecycle-checkpoints"]["status"], "passed")
            self.assertEqual(checks["web-interface"]["status"], "passed")
            self.assertEqual(checks["contract-evolution"]["status"], "passed")
            self.assertIn(
                "capability.web-interface",
                payload["resolved_components"],
            )
            self.assertIn(
                "lifecycle.implementation-evidence",
                payload["resolved_components"],
            )
            self.assertIn(
                "lifecycle.lifecycle-checkpoints",
                payload["resolved_components"],
            )


if __name__ == "__main__":
    unittest.main()
