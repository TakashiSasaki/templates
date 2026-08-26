from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from executable_proof_test_support import (
    materialize_declared_harnesses,
    upgrade_product_evidence_v6,
)
from lifecycle_checkpoint_test_support import (
    create_planning_checkpoint,
    planning_evidence_from_product,
)

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "capability.mcp"
SCHEMA = COMPONENT / "files" / "schemas" / "mcp-interface.schema.json"
SEED = COMPONENT / "files" / "contracts" / "mcp-interface.json"
VALIDATOR = COMPONENT / "files" / ".template-composition" / "validators" / "validate_mcp_interface.py"
COMPOSER = ROOT / "scripts" / "compose.py"


class McpInterfaceContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def product_contract(self) -> dict:
        return {
            "$schema": "../schemas/mcp-interface.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "protocolRevision": "2026-07-28",
            "transports": [{"id": "stdio", "kind": "stdio", "protocolProbe": "Start the runtime-owned stdio server and perform MCP discovery using 2026-07-28 request metadata.", "success": "Discovery returns the selected server metadata.", "negative": "Unsupported revision metadata is rejected explicitly."}],
            "operations": [{"id": "stdio-list-records", "kind": "tool", "name": "records.list", "transportId": "stdio", "success": "Valid arguments return the record collection.", "negative": "Invalid arguments return a bounded protocol/domain error."}],
        }

    def evidence(self, *, proof_kind: str = "integration-test", requirement_kind: str | None = None, proof_status: str = "verified") -> dict:
        required_kind = requirement_kind or proof_kind
        command = {"id": "mcp-proof", "command": "python -m unittest tests.test_mcp_contract", "purpose": "Exercise MCP discovery, negative protocol behavior, and tool calls."}
        gate = {"id": "release", "purpose": "Run executable MCP protocol proof.", "commandIds": ["mcp-proof"]}
        def record(record_id: str, item_kind: str, item_id: str, positive_id: str, negative_id: str) -> dict:
            return {
                "id": record_id,
                "target": {"kind": "contract-item", "contractId": "mcp_interface", "itemKind": item_kind, "itemId": item_id},
                "implementationBoundary": {"status": "verified", "description": "MCP adapter boundary.", "locator": "app/mcp.py"},
                "positiveEvidence": [{"id": positive_id, "status": proof_status, "kind": proof_kind, "description": "Execute the documented successful MCP path.", "locator": "tests/test_mcp_contract.py", "commandId": "mcp-proof", "expectedResult": "documented MCP success behavior"}],
                "negativeEvidence": [{"id": negative_id, "status": proof_status, "kind": proof_kind, "description": "Execute the documented negative MCP path.", "locator": "tests/test_mcp_contract.py", "commandId": "mcp-proof", "expectedResult": "documented MCP rejection/error behavior"}],
                "releaseGateIds": ["release"],
            }
        transport_record_id = "mcp-interface-transport-stdio"
        operation_record_id = "mcp-interface-operation-stdio-list-records"
        value = {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 5,
            "mode": "product",
            "commands": [command],
            "releaseGates": [gate],
            "requirements": [
                {"id": "REQ-MCP-TRANSPORT", "description": "The selected MCP transport completes a real protocol round trip and rejects unsupported protocol metadata.", "recordIds": [transport_record_id], "requiredPositiveProofKinds": [required_kind]},
                {"id": "REQ-MCP-LIST", "description": "The records.list MCP operation executes through the declared transport for callers.", "recordIds": [operation_record_id], "requiredPositiveProofKinds": [required_kind]},
            ],
            "records": [record(transport_record_id, "transport", "stdio", "mcp-transport-positive", "mcp-transport-negative"), record(operation_record_id, "operation", "stdio-list-records", "mcp-operation-positive", "mcp-operation-negative")],
        }
        return upgrade_product_evidence_v6(
            value,
            harness_by_command={"mcp-proof": "tests/test_mcp_contract.py"},
        )

    def run_validator(self, contract: dict, evidence: dict) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/mcp-interface.json", contract)
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_descriptor_registers_machine_contract_and_evidence_dependency(self) -> None:
        descriptor = json.loads((COMPONENT / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["version"], 4)
        self.assertEqual(descriptor["requires"], ["capability.runtime", "lifecycle.implementation-evidence"])
        registrations = {entry["id"]: entry for entry in descriptor["contract_registrations"]}
        self.assertIn("mcp_interface", registrations)
        self.assertEqual(registrations["mcp_interface"]["document"], "contracts/mcp-interface.json")
        self.assertEqual(registrations["mcp_interface"]["document_schema_version"], 2)

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.product_contract())

    def test_transport_and_operation_require_executable_positive_negative_proof(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("executable proof strength: OK", result.stdout)
        weak_proof = self.run_validator(self.product_contract(), self.evidence(proof_kind="inspection", requirement_kind="integration-test"))
        self.assertNotEqual(weak_proof.returncode, 0)
        self.assertIn("executable proof kind", weak_proof.stderr)
        self.assertIn("static inspection or unit-only proof is insufficient", weak_proof.stderr)
        weak_requirement = self.run_validator(self.product_contract(), self.evidence(proof_kind="integration-test", requirement_kind="inspection"))
        self.assertNotEqual(weak_requirement.returncode, 0)
        self.assertIn("requiredPositiveProofKinds", weak_requirement.stderr)

    def test_deferred_executable_proof_is_truthful_but_not_erased(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence(proof_status="deferred"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_product_evidence_cannot_hide_selected_mcp_in_template_mode(self) -> None:
        result = self.run_validator(json.loads(SEED.read_text(encoding="utf-8")), self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remains in template mode while product implementation evidence is active", result.stderr)

    def test_missing_unknown_and_duplicate_targets_fail_closed(self) -> None:
        evidence = self.evidence()
        missing = deepcopy(evidence)
        missing["records"] = missing["records"][:1]
        result = self.run_validator(self.product_contract(), missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing MCP implementation-evidence target", result.stderr)
        unknown = deepcopy(evidence)
        unknown["records"][1]["target"]["itemId"] = "other-operation"
        result = self.run_validator(self.product_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing MCP implementation-evidence target", result.stderr)
        self.assertIn("unknown MCP implementation-evidence target", result.stderr)
        duplicate = deepcopy(evidence)
        second = deepcopy(duplicate["records"][1])
        second["id"] = "mcp-interface-operation-duplicate"
        duplicate["records"].append(second)
        result = self.run_validator(self.product_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)

    def test_operation_must_bind_to_selected_transport_and_unique_exposure(self) -> None:
        unknown_transport = self.product_contract()
        unknown_transport["operations"][0]["transportId"] = "http"
        result = self.run_validator(unknown_transport, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references unknown transportId", result.stderr)
        duplicate = self.product_contract()
        second = deepcopy(duplicate["operations"][0])
        second["id"] = "stdio-list-records-copy"
        duplicate["operations"].append(second)
        result = self.run_validator(duplicate, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate MCP operation exposure", result.stderr)

    def test_selected_product_mcp_passes_materialized_consumer_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(config, {"schema_version": 1, "recipe": "skill", "components": {"include": ["capability.mcp"], "exclude": []}, "parameters": {}})
            apply_result = subprocess.run([sys.executable, str(COMPOSER), "apply", "--config", str(config), "--target", str(target)], cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(apply_result.returncode, 0, apply_result.stdout + apply_result.stderr)

            product_evidence, planning_evidence = planning_evidence_from_product(
                self.evidence()
            )
            planning_contract = {
                "$schema": "../schemas/mcp-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "protocolRevision": "2026-07-28",
                "transports": [
                    {
                        "id": "stdio",
                        "kind": "stdio",
                        "purpose": "Expose the selected stdio MCP transport.",
                    }
                ],
                "operations": [
                    {
                        "id": "stdio-list-records",
                        "kind": "tool",
                        "transportId": "stdio",
                        "purpose": "Expose records.list through the selected transport.",
                    }
                ],
            }
            self.write_json(target / "contracts" / "mcp-interface.json", planning_contract)
            self.write_json(target / "contracts" / "implementation-evidence.json", planning_evidence)
            create_planning_checkpoint(target)

            self.write_json(target / "contracts" / "mcp-interface.json", self.product_contract())
            self.write_json(target / "contracts" / "implementation-evidence.json", product_evidence)
            materialize_declared_harnesses(target, product_evidence)
            runner = target / ".template-composition" / "validate.py"
            validate_result = subprocess.run([sys.executable, str(runner), str(target), "--format", "json"], cwd=target, text=True, capture_output=True, check=False)
            try:
                payload = json.loads(validate_result.stdout)
            except json.JSONDecodeError as exc:
                self.fail(f"consumer validator did not emit JSON: {exc}\nstdout={validate_result.stdout}\nstderr={validate_result.stderr}")
            self.assertEqual(validate_result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            self.assertEqual(checks["lifecycle-checkpoints"]["status"], "passed")
            self.assertEqual(checks["mcp-interface"]["status"], "passed")
            self.assertEqual(checks["contract-evolution"]["status"], "passed")
            self.assertIn("capability.mcp", payload["resolved_components"])
            self.assertIn("lifecycle.implementation-evidence", payload["resolved_components"])
            self.assertIn("lifecycle.lifecycle-checkpoints", payload["resolved_components"])


if __name__ == "__main__":
    unittest.main()
