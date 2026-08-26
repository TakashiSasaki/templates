from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class PlanningTargetProofStrengthTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def target(self, contract_id: str, item_kind: str, item_id: str) -> dict:
        return {
            "kind": "contract-item",
            "contractId": contract_id,
            "itemKind": item_kind,
            "itemId": item_id,
        }

    def planning_evidence(self) -> dict:
        entries = [
            (
                "REQ-PLAN-WEBAPP-ROUTE",
                self.target("routes", "route", "home"),
                "end-to-end-test",
            ),
            (
                "REQ-PLAN-CLI",
                self.target("cli_interface", "entrypoint", "records"),
                "integration-test",
            ),
            (
                "REQ-PLAN-SERVICE",
                self.target("service_interface", "operation", "records-list"),
                "integration-test",
            ),
            (
                "REQ-PLAN-WEB-INTERFACE",
                self.target("web_interface", "endpoint", "records-page"),
                "end-to-end-test",
            ),
            (
                "REQ-PLAN-MCP-TRANSPORT",
                self.target("mcp_interface", "transport", "stdio"),
                "integration-test",
            ),
            (
                "REQ-PLAN-MCP-OPERATION",
                self.target("mcp_interface", "operation", "records-list"),
                "integration-test",
            ),
            (
                "REQ-PLAN-MCP-APPS-EXTENSION",
                self.target("mcp_apps", "extension", "mcp-apps"),
                "integration-test",
            ),
            (
                "REQ-PLAN-MCP-APPS-VIEW",
                self.target("mcp_apps", "view", "records-view"),
                "accessibility-test",
            ),
            (
                "REQ-PLAN-MCP-APPS-ASSOCIATION",
                self.target("mcp_apps", "association", "records-list-ui"),
                "end-to-end-test",
            ),
        ]
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 5,
            "mode": "planning",
            "commands": [],
            "releaseGates": [],
            "records": [],
            "requirements": [
                {
                    "id": requirement_id,
                    "description": f"Planning obligation for {requirement_id}.",
                    "targets": [target],
                    "recordIds": [],
                    "requiredPositiveProofKinds": [proof_kind],
                }
                for requirement_id, target, proof_kind in entries
            ],
        }

    def materialize(self, root: Path) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {
                    "include": [
                        "capability.cli",
                        "capability.service",
                        "capability.web-interface",
                        "capability.mcp-apps",
                    ],
                    "exclude": [],
                },
                "parameters": {},
            },
        )
        result = subprocess.run(
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
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def validate(self, target: Path, evidence: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
        self.write_json(target / "contracts" / "implementation-evidence.json", evidence)
        runner = target / ".template-composition" / "validate.py"
        result = subprocess.run(
            [sys.executable, str(runner), str(target), "--format", "json"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"consumer validator did not emit JSON: {exc}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def requirement(self, evidence: dict, requirement_id: str) -> dict:
        return next(
            requirement
            for requirement in evidence["requirements"]
            if requirement["id"] == requirement_id
        )

    def test_strong_target_bound_plan_passes_every_selected_validator_and_worklist_keeps_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            evidence = self.planning_evidence()
            result, payload = self.validate(target, evidence)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            for check_id in (
                "implementation-evidence",
                "webapp-implementation-coverage",
                "cli-interface",
                "service-interface",
                "web-interface",
                "mcp-interface",
                "mcp-apps",
            ):
                self.assertEqual(checks[check_id]["status"], "passed", checks[check_id])
            self.assertIn("planning targets", checks["cli-interface"]["stdout"])
            self.assertIn("planning targets", checks["mcp-apps"]["stdout"])

            scaffold = subprocess.run(
                [sys.executable, "scripts/scaffold_webapp_evidence.py"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
            worklist = json.loads(scaffold.stdout)
            projected = {item["id"]: item for item in worklist["requirements"]}
            self.assertEqual(
                projected["REQ-PLAN-WEBAPP-ROUTE"]["targets"],
                [self.target("routes", "route", "home")],
            )
            self.assertEqual(
                projected["REQ-PLAN-CLI"]["targets"],
                [self.target("cli_interface", "entrypoint", "records")],
            )

    def test_weak_planning_proof_kinds_fail_at_the_owning_validator_before_coding(self) -> None:
        cases = [
            ("REQ-PLAN-WEBAPP-ROUTE", "integration-test", "webapp-implementation-coverage"),
            ("REQ-PLAN-CLI", "inspection", "cli-interface"),
            ("REQ-PLAN-SERVICE", "unit-test", "service-interface"),
            ("REQ-PLAN-WEB-INTERFACE", "inspection", "web-interface"),
            ("REQ-PLAN-MCP-TRANSPORT", "inspection", "mcp-interface"),
            ("REQ-PLAN-MCP-APPS-EXTENSION", "unit-test", "mcp-apps"),
            ("REQ-PLAN-MCP-APPS-VIEW", "integration-test", "mcp-apps"),
            ("REQ-PLAN-MCP-APPS-ASSOCIATION", "accessibility-test", "mcp-apps"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            for requirement_id, weak_kind, expected_check in cases:
                with self.subTest(requirement_id=requirement_id, weak_kind=weak_kind):
                    evidence = self.planning_evidence()
                    self.requirement(evidence, requirement_id)[
                        "requiredPositiveProofKinds"
                    ] = [weak_kind]
                    result, payload = self.validate(target, evidence)
                    self.assertNotEqual(result.returncode, 0, payload)
                    checks = {check["id"]: check for check in payload["checks"]}
                    self.assertEqual(
                        checks[expected_check]["status"], "failed", checks[expected_check]
                    )
                    self.assertIn("requiredPositiveProofKinds", checks[expected_check]["stderr"])

    def test_invalid_planning_target_families_fail_closed(self) -> None:
        cases = [
            ("REQ-PLAN-CLI", "operation", "cli-interface"),
            ("REQ-PLAN-SERVICE", "endpoint", "service-interface"),
            ("REQ-PLAN-WEB-INTERFACE", "route", "web-interface"),
            ("REQ-PLAN-MCP-OPERATION", "endpoint", "mcp-interface"),
            ("REQ-PLAN-MCP-APPS-VIEW", "widget", "mcp-apps"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            for requirement_id, invalid_item_kind, expected_check in cases:
                with self.subTest(requirement_id=requirement_id):
                    evidence = self.planning_evidence()
                    self.requirement(evidence, requirement_id)["targets"][0][
                        "itemKind"
                    ] = invalid_item_kind
                    result, payload = self.validate(target, evidence)
                    self.assertNotEqual(result.returncode, 0, payload)
                    checks = {check["id"]: check for check in payload["checks"]}
                    self.assertEqual(
                        checks[expected_check]["status"], "failed", checks[expected_check]
                    )
                    self.assertIn("unsupported target", checks[expected_check]["stderr"])

    def test_unknown_webapp_planning_item_and_wrong_apps_extension_id_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))

            unknown_webapp = self.planning_evidence()
            self.requirement(unknown_webapp, "REQ-PLAN-WEBAPP-ROUTE")["targets"][0][
                "itemId"
            ] = "not-a-route"
            result, payload = self.validate(target, unknown_webapp)
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["webapp-implementation-coverage"]["status"], "failed")
            self.assertIn(
                "unknown planning Webapp requirement target",
                checks["webapp-implementation-coverage"]["stderr"],
            )

            wrong_extension = self.planning_evidence()
            self.requirement(wrong_extension, "REQ-PLAN-MCP-APPS-EXTENSION")["targets"][0][
                "itemId"
            ] = "other-extension"
            result, payload = self.validate(target, wrong_extension)
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["mcp-apps"]["status"], "failed")
            self.assertIn("stable extension target id", checks["mcp-apps"]["stderr"])


if __name__ == "__main__":
    unittest.main()
