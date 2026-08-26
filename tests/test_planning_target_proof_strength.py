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
            ("REQ-PLAN-WEBAPP-ROUTE", self.target("routes", "route", "home"), "end-to-end-test"),
            ("REQ-PLAN-CLI", self.target("cli_interface", "entrypoint", "records"), "integration-test"),
            ("REQ-PLAN-SERVICE", self.target("service_interface", "operation", "records-list"), "integration-test"),
            ("REQ-PLAN-WEB-INTERFACE", self.target("web_interface", "endpoint", "records-page"), "end-to-end-test"),
            ("REQ-PLAN-MCP-TRANSPORT", self.target("mcp_interface", "transport", "stdio"), "integration-test"),
            ("REQ-PLAN-MCP-OPERATION", self.target("mcp_interface", "operation", "records-list"), "integration-test"),
            ("REQ-PLAN-MCP-APPS-EXTENSION", self.target("mcp_apps", "extension", "mcp-apps"), "integration-test"),
            ("REQ-PLAN-MCP-APPS-VIEW", self.target("mcp_apps", "view", "records-view"), "accessibility-test"),
            ("REQ-PLAN-MCP-APPS-ASSOCIATION", self.target("mcp_apps", "association", "records-list-ui"), "end-to-end-test"),
        ]
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 6,
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

    def planning_contracts(self) -> dict[str, dict]:
        return {
            "cli-interface.json": {
                "$schema": "../schemas/cli-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "entrypoints": [{"id": "records", "purpose": "Expose record operations to CLI callers."}],
            },
            "service-interface.json": {
                "$schema": "../schemas/service-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "protocol": "http-json",
                "operations": [{"id": "records-list", "purpose": "List records through the service boundary."}],
            },
            "web-interface.json": {
                "$schema": "../schemas/web-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "endpoints": [{"id": "records-page", "kind": "browser-page", "purpose": "Render the records page in a browser."}],
            },
            "mcp-interface.json": {
                "$schema": "../schemas/mcp-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "protocolRevision": "2026-07-28",
                "transports": [{"id": "stdio", "kind": "stdio", "purpose": "Expose the local MCP transport."}],
                "operations": [{"id": "records-list", "kind": "tool", "transportId": "stdio", "purpose": "List records through MCP."}],
            },
            "mcp-apps.json": {
                "$schema": "../schemas/mcp-apps.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "extension": {"id": "mcp-apps", "identifier": "io.modelcontextprotocol/ui", "revision": "2026-01-26"},
                "views": [{"id": "records-view", "purpose": "Render records in an MCP App View."}],
                "associations": [{"id": "records-list-ui", "operationId": "records-list", "viewId": "records-view", "purpose": "Bind the list tool to its View."}],
            },
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
                    "include": ["capability.cli", "capability.service", "capability.web-interface", "capability.mcp-apps"],
                    "exclude": [],
                },
                "parameters": {},
            },
        )
        result = subprocess.run(
            [sys.executable, str(COMPOSER), "apply", "--config", str(config), "--target", str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, contract in self.planning_contracts().items():
            self.write_json(target / "contracts" / name, contract)
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
            self.fail(f"consumer validator did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result, payload

    def requirement(self, evidence: dict, requirement_id: str) -> dict:
        return next(requirement for requirement in evidence["requirements"] if requirement["id"] == requirement_id)

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
            self.assertIn("planned entrypoint authority", checks["cli-interface"]["stdout"])
            self.assertIn("planned item authority", checks["mcp-apps"]["stdout"])

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
            self.assertEqual(projected["REQ-PLAN-WEBAPP-ROUTE"]["targets"], [self.target("routes", "route", "home")])
            self.assertEqual(projected["REQ-PLAN-CLI"]["targets"], [self.target("cli_interface", "entrypoint", "records")])

    def test_weak_planning_proof_kinds_fail_at_the_owning_validator_before_coding(self) -> None:
        cases = [
            ("REQ-PLAN-WEBAPP-ROUTE", "integration-test", "webapp-implementation-coverage"),
            ("REQ-PLAN-CLI", "inspection", "cli-interface"),
            ("REQ-PLAN-SERVICE", "unit-test", "service-interface"),
            ("REQ-PLAN-WEB-INTERFACE", "integration-test", "web-interface"),
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
                    self.requirement(evidence, requirement_id)["requiredPositiveProofKinds"] = [weak_kind]
                    result, payload = self.validate(target, evidence)
                    self.assertNotEqual(result.returncode, 0, payload)
                    checks = {check["id"]: check for check in payload["checks"]}
                    self.assertEqual(checks[expected_check]["status"], "failed", checks[expected_check])
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
                    self.requirement(evidence, requirement_id)["targets"][0]["itemKind"] = invalid_item_kind
                    result, payload = self.validate(target, evidence)
                    self.assertNotEqual(result.returncode, 0, payload)
                    checks = {check["id"]: check for check in payload["checks"]}
                    self.assertEqual(checks[expected_check]["status"], "failed", checks[expected_check])
                    self.assertIn("unsupported target", checks[expected_check]["stderr"])

    def test_phantom_capability_item_ids_fail_closed_before_coding(self) -> None:
        cases = [
            ("REQ-PLAN-CLI", "cli-interface"),
            ("REQ-PLAN-SERVICE", "service-interface"),
            ("REQ-PLAN-WEB-INTERFACE", "web-interface"),
            ("REQ-PLAN-MCP-TRANSPORT", "mcp-interface"),
            ("REQ-PLAN-MCP-OPERATION", "mcp-interface"),
            ("REQ-PLAN-MCP-APPS-VIEW", "mcp-apps"),
            ("REQ-PLAN-MCP-APPS-ASSOCIATION", "mcp-apps"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            for requirement_id, expected_check in cases:
                with self.subTest(requirement_id=requirement_id):
                    evidence = self.planning_evidence()
                    self.requirement(evidence, requirement_id)["targets"][0]["itemId"] = "phantom-item"
                    result, payload = self.validate(target, evidence)
                    self.assertNotEqual(result.returncode, 0, payload)
                    checks = {check["id"]: check for check in payload["checks"]}
                    self.assertEqual(checks[expected_check]["status"], "failed", checks[expected_check])
                    self.assertIn("undeclared planned", checks[expected_check]["stderr"])

    def test_planned_items_cannot_be_omitted_from_requirement_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            evidence = self.planning_evidence()
            evidence["requirements"] = [req for req in evidence["requirements"] if req["id"] != "REQ-PLAN-SERVICE"]
            result, payload = self.validate(target, evidence)
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["service-interface"]["status"], "failed")
            self.assertIn("missing a planning requirement target", checks["service-interface"]["stderr"])

    def test_planning_evidence_rejects_template_capability_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            contract = self.planning_contracts()["cli-interface.json"]
            contract["mode"] = "template"
            contract["entrypoints"] = []
            self.write_json(target / "contracts" / "cli-interface.json", contract)
            result, payload = self.validate(target, self.planning_evidence())
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["cli-interface"]["status"], "failed")
            self.assertIn("authoritative before coding", checks["cli-interface"]["stderr"])

    def test_planning_relationships_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            mcp = self.planning_contracts()["mcp-interface.json"]
            mcp["operations"][0]["transportId"] = "missing-transport"
            self.write_json(target / "contracts" / "mcp-interface.json", mcp)
            result, payload = self.validate(target, self.planning_evidence())
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["mcp-interface"]["status"], "failed")
            self.assertIn("unknown transportId", checks["mcp-interface"]["stderr"])

            for name, contract in self.planning_contracts().items():
                self.write_json(target / "contracts" / name, contract)
            apps = self.planning_contracts()["mcp-apps.json"]
            apps["associations"][0]["operationId"] = "missing-tool"
            self.write_json(target / "contracts" / "mcp-apps.json", apps)
            result, payload = self.validate(target, self.planning_evidence())
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["mcp-apps"]["status"], "failed")
            self.assertIn("unknown or non-tool planned MCP operation", checks["mcp-apps"]["stderr"])

    def test_unknown_webapp_planning_item_and_wrong_apps_extension_id_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            unknown_webapp = self.planning_evidence()
            self.requirement(unknown_webapp, "REQ-PLAN-WEBAPP-ROUTE")["targets"][0]["itemId"] = "not-a-route"
            result, payload = self.validate(target, unknown_webapp)
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["webapp-implementation-coverage"]["status"], "failed")
            self.assertIn("unknown planning Webapp requirement target", checks["webapp-implementation-coverage"]["stderr"])

            wrong_extension = self.planning_evidence()
            self.requirement(wrong_extension, "REQ-PLAN-MCP-APPS-EXTENSION")["targets"][0]["itemId"] = "other-extension"
            result, payload = self.validate(target, wrong_extension)
            self.assertNotEqual(result.returncode, 0, payload)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["mcp-apps"]["status"], "failed")
            self.assertIn("stable extension target id", checks["mcp-apps"]["stderr"])


if __name__ == "__main__":
    unittest.main()
