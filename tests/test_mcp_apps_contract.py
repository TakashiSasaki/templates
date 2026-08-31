from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "capability.mcp-apps"
SCHEMA = COMPONENT / "files" / "schemas" / "mcp-apps.schema.json"
SEED = COMPONENT / "files" / "contracts" / "mcp-apps.json"
VALIDATOR = COMPONENT / "files" / ".template-composition" / "validators" / "validate_mcp_apps.py"
COMPOSER = ROOT / "scripts" / "compose.py"


class McpAppsContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def apps_contract(self) -> dict:
        return {
            "$schema": "../schemas/mcp-apps.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "extension": {"id": "mcp-apps", "identifier": "io.modelcontextprotocol/ui", "revision": "2026-01-26", "success": "The server advertises the selected MCP Apps extension revision.", "negative": "A Host without Apps support receives the documented core fallback."},
            "views": [{"id": "records-view", "resourceUri": "ui://records/list", "mediaType": "text/html;profile=mcp-app", "success": "The Host renders the declared records View through the Apps bridge.", "negative": "View bootstrap failure leaves the core MCP result intact."}],
            "associations": [{"id": "records-list-ui", "operationId": "stdio-list-records", "viewId": "records-view", "success": "The records.list tool advertises and opens the declared View.", "negative": "An unavailable View degrades to the documented core result."}],
        }

    def mcp_contract(self, *, operation_kind: str = "tool") -> dict:
        return {
            "$schema": "../schemas/mcp-interface.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "protocolRevision": "2026-07-28",
            "transports": [{"id": "stdio", "kind": "stdio"}],
            "operations": [{"id": "stdio-list-records", "kind": operation_kind, "name": "records.list", "transportId": "stdio"}],
        }

    def evidence(self) -> dict:
        kinds = {"extension": "integration-test", "view": "accessibility-test", "association": "end-to-end-test"}
        targets = [("apps-extension", "extension", "mcp-apps"), ("apps-view", "view", "records-view"), ("apps-association", "association", "records-list-ui")]
        records = []
        requirements = []
        for record_id, item_kind, item_id in targets:
            kind = kinds[item_kind]
            records.append({"id": record_id, "target": {"kind": "contract-item", "contractId": "mcp_apps", "itemKind": item_kind, "itemId": item_id}, "implementationBoundary": {"status": "verified", "description": "MCP Apps adapter boundary.", "locator": "app/mcp_apps.py"}, "positiveEvidence": [{"id": record_id + "-positive", "status": "verified", "kind": kind}], "negativeEvidence": [{"id": record_id + "-negative", "status": "verified", "kind": kind}], "releaseGateIds": ["release"]})
            requirements.append({"id": "REQ-" + record_id.upper().replace("-", "_"), "recordIds": [record_id], "requiredPositiveProofKinds": [kind]})
        return {"$schema": "../schemas/implementation-evidence.schema.json", "schemaVersion": 5, "mode": "product", "requirements": requirements, "records": records}

    def run_validator(self, apps: dict, evidence: dict, mcp: dict | None = None) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/mcp-apps.json", apps)
        self.write_json(root / "contracts/mcp-interface.json", mcp or self.mcp_contract())
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_descriptor_registers_machine_contract(self) -> None:
        descriptor = json.loads((COMPONENT / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["version"], 5)
        self.assertEqual(descriptor["requires"], ["capability.mcp"])
        registrations = {entry["id"]: entry for entry in descriptor["contract_registrations"]}
        self.assertEqual(registrations["mcp_apps"]["document"], "contracts/mcp-apps.json")
        self.assertEqual(registrations["mcp_apps"]["schema"], "schemas/mcp-apps.schema.json")
        self.assertEqual(registrations["mcp_apps"]["document_schema_version"], 2)

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.apps_contract())

    def test_product_apps_requires_target_specific_proof_strength(self) -> None:
        result = self.run_validator(self.apps_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        weak_view = self.evidence()
        weak_view["records"][1]["positiveEvidence"][0]["kind"] = "inspection"
        result = self.run_validator(self.apps_contract(), weak_view)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MCP Apps view", result.stderr)
        self.assertIn("accessibility-test", result.stderr)
        weak_association = self.evidence()
        weak_association["records"][2]["positiveEvidence"][0]["kind"] = "integration-test"
        result = self.run_validator(self.apps_contract(), weak_association)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MCP Apps association", result.stderr)
        self.assertIn("end-to-end-test", result.stderr)
        weak_requirement = self.evidence()
        weak_requirement["requirements"][2]["requiredPositiveProofKinds"] = ["integration-test"]
        result = self.run_validator(self.apps_contract(), weak_requirement)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compatible proof strength", result.stderr)

    def test_association_must_reference_core_tool_and_declared_view(self) -> None:
        unknown_operation = self.apps_contract()
        unknown_operation["associations"][0]["operationId"] = "missing-tool"
        result = self.run_validator(unknown_operation, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown or non-tool MCP operation", result.stderr)
        non_tool = self.run_validator(self.apps_contract(), self.evidence(), self.mcp_contract(operation_kind="resource"))
        self.assertNotEqual(non_tool.returncode, 0)
        self.assertIn("unknown or non-tool MCP operation", non_tool.stderr)
        unknown_view = self.apps_contract()
        unknown_view["associations"][0]["viewId"] = "missing-view"
        result = self.run_validator(unknown_view, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references unknown view", result.stderr)
        self.assertIn("is not referenced by any tool association", result.stderr)

    def test_missing_unknown_and_duplicate_apps_targets_fail_closed(self) -> None:
        missing = self.evidence()
        missing["records"] = missing["records"][:-1]
        result = self.run_validator(self.apps_contract(), missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing MCP Apps implementation-evidence target", result.stderr)
        unknown = self.evidence()
        unknown["records"][2]["target"]["itemId"] = "other-association"
        result = self.run_validator(self.apps_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown MCP Apps implementation-evidence target", result.stderr)
        duplicate = self.evidence()
        second = deepcopy(duplicate["records"][2])
        second["id"] = "apps-association-copy"
        duplicate["records"].append(second)
        result = self.run_validator(self.apps_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)

    def test_product_evidence_cannot_hide_apps_in_template_mode(self) -> None:
        result = self.run_validator(json.loads(SEED.read_text(encoding="utf-8")), self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remains in template mode while product implementation evidence is active", result.stderr)

    def test_selected_apps_materializes_contract_and_validator_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(config, {"schema_version": 1, "recipe": "skill", "components": {"include": ["capability.mcp-apps"], "exclude": []}, "parameters": {}})
            applied = subprocess.run([sys.executable, str(COMPOSER), "apply", "--config", str(config), "--target", str(target)], cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            runner = target / ".template-composition" / "validate.py"
            validated = subprocess.run([sys.executable, str(runner), str(target), "--format", "json"], cwd=target, text=True, capture_output=True, check=False)
            payload = json.loads(validated.stdout)
            self.assertEqual(validated.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            components = set(payload["resolved_components"])
            self.assertIn("capability.mcp-apps", components)
            self.assertIn("capability.mcp", components)
            self.assertIn("lifecycle.implementation-evidence", components)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["mcp-interface"]["status"], "passed")
            self.assertEqual(checks["mcp-apps"]["status"], "passed")
            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            manifest = json.loads((target / "contracts/manifest.json").read_text(encoding="utf-8"))
            contract_ids = {entry["id"] for entry in manifest["contracts"]}
            self.assertIn("mcp_interface", contract_ids)
            self.assertIn("mcp_apps", contract_ids)
            self.assertEqual(json.loads((target / "contracts/mcp-apps.json").read_text(encoding="utf-8"))["mode"], "template")


if __name__ == "__main__":
    unittest.main()
