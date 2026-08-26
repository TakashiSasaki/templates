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
COMPONENT = ROOT / "components" / "capability.service"
SCHEMA = COMPONENT / "files" / "schemas" / "service-interface.schema.json"
SEED = COMPONENT / "files" / "contracts" / "service-interface.json"
VALIDATOR = COMPONENT / "files" / ".template-composition" / "validators" / "validate_service_interface.py"


class ServiceInterfaceContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def product_contract(self) -> dict:
        return {
            "$schema": "../schemas/service-interface.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "protocol": "http-json",
            "operations": [
                {
                    "id": "list-records",
                    "invocation": "GET /api/records",
                    "success": "200 JSON record array",
                    "negative": "400 JSON error for invalid query",
                }
            ],
        }

    def evidence(self, *, proof_kind: str = "integration-test", requirement_kind: str | None = None) -> dict:
        required_kind = requirement_kind or proof_kind
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 3,
            "mode": "product",
            "commands": [{"id": "service-proof", "command": "python -m unittest tests.test_service", "purpose": "Exercise the public service boundary."}],
            "releaseGates": [{"id": "release", "purpose": "Run executable service proof.", "commandIds": ["service-proof"]}],
            "requirements": [{"id": "REQ-SERVICE-LIST", "description": "The maintained service operation executes for callers.", "recordIds": ["service-interface-operation-list-records"], "requiredPositiveProofKinds": [required_kind]}],
            "records": [
                {
                    "id": "service-interface-operation-list-records",
                    "target": {"kind": "contract-item", "contractId": "service_interface", "itemKind": "operation", "itemId": "list-records"},
                    "implementationBoundary": {"status": "verified", "description": "HTTP service adapter.", "locator": "app/service.py"},
                    "positiveEvidence": [{"id": "service-positive", "status": "verified", "kind": proof_kind, "description": "Execute a valid service request.", "locator": "tests/test_service.py", "commandId": "service-proof", "expectedResult": "documented success response"}],
                    "negativeEvidence": [{"id": "service-negative", "status": "verified", "kind": proof_kind, "description": "Execute an invalid service request.", "locator": "tests/test_service.py", "commandId": "service-proof", "expectedResult": "documented error response"}],
                    "releaseGateIds": ["release"],
                }
            ],
        }

    def run_validator(self, contract: dict, evidence: dict) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/service-interface.json", contract)
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.product_contract())

    def test_product_service_requires_executable_positive_negative_and_requirement_strength(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("executable evidence strength: OK", result.stdout)

        weak_proof = self.run_validator(self.product_contract(), self.evidence(proof_kind="inspection", requirement_kind="integration-test"))
        self.assertNotEqual(weak_proof.returncode, 0)
        self.assertIn("executable proof kind", weak_proof.stderr)
        self.assertIn("static inspection or unit-only proof is insufficient", weak_proof.stderr)

        weak_requirement = self.run_validator(self.product_contract(), self.evidence(proof_kind="integration-test", requirement_kind="inspection"))
        self.assertNotEqual(weak_requirement.returncode, 0)
        self.assertIn("requiredPositiveProofKinds", weak_requirement.stderr)

    def test_product_evidence_cannot_hide_selected_service_in_template_mode(self) -> None:
        result = self.run_validator(json.loads(SEED.read_text(encoding="utf-8")), self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remains in template mode while product implementation evidence is active", result.stderr)

    def test_unknown_duplicate_and_missing_service_operation_targets_fail_closed(self) -> None:
        evidence = self.evidence()
        unknown = deepcopy(evidence)
        unknown["records"][0]["target"]["itemId"] = "other"
        result = self.run_validator(self.product_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing service implementation-evidence target", result.stderr)
        self.assertIn("unknown service implementation-evidence target", result.stderr)

        duplicate = deepcopy(evidence)
        second = deepcopy(duplicate["records"][0])
        second["id"] = "service-interface-operation-list-records-duplicate"
        duplicate["records"].append(second)
        result = self.run_validator(self.product_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)


if __name__ == "__main__":
    unittest.main()
