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
COMPONENT = ROOT / "components" / "capability.web-interface"
SCHEMA = COMPONENT / "files" / "schemas" / "web-interface.schema.json"
SEED = COMPONENT / "files" / "contracts" / "web-interface.json"
VALIDATOR = (
    COMPONENT
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_web_interface.py"
)


class WebInterfaceContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def product_contract(self) -> dict:
        return {
            "$schema": "../schemas/web-interface.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "endpoints": [
                {
                    "id": "ui",
                    "kind": "browser-page",
                    "method": "GET",
                    "path": "/ui",
                    "purpose": "Standalone caller-visible browser interface.",
                },
                {
                    "id": "verify-api",
                    "kind": "backend-api",
                    "method": "POST",
                    "path": "/api/verify",
                    "purpose": "Backend operation used by the standalone browser interface.",
                },
                {
                    "id": "health",
                    "kind": "health",
                    "method": "GET",
                    "path": "/health",
                    "purpose": "Standalone Web interface readiness endpoint.",
                },
            ],
        }

    def evidence(
        self,
        *,
        browser_proof_kind: str = "end-to-end-test",
        api_proof_kind: str = "integration-test",
        health_proof_kind: str = "integration-test",
        browser_requirement_kind: str | None = None,
        api_requirement_kind: str | None = None,
        health_requirement_kind: str | None = None,
    ) -> dict:
        values = {
            "ui": (
                browser_proof_kind,
                browser_requirement_kind or browser_proof_kind,
            ),
            "verify-api": (
                api_proof_kind,
                api_requirement_kind or api_proof_kind,
            ),
            "health": (
                health_proof_kind,
                health_requirement_kind or health_proof_kind,
            ),
        }
        records: list[dict] = []
        requirements: list[dict] = []
        for endpoint_id, (proof_kind, requirement_kind) in values.items():
            record_id = f"web-interface-endpoint-{endpoint_id}"
            requirements.append(
                {
                    "id": f"REQ-WEB-{endpoint_id.upper()}",
                    "description": f"The {endpoint_id} endpoint is caller-visible.",
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": [requirement_kind],
                }
            )
            records.append(
                {
                    "id": record_id,
                    "target": {
                        "kind": "contract-item",
                        "contractId": "web_interface",
                        "itemKind": "endpoint",
                        "itemId": endpoint_id,
                    },
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "Standalone Web interface adapter.",
                        "locator": "app.py",
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{endpoint_id}-positive",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": "Exercise the endpoint successfully.",
                            "locator": "tests/test_web_interface.py",
                            "commandId": "web-proof",
                            "expectedResult": "caller-visible success behavior is observed",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{endpoint_id}-negative",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": "Exercise an endpoint failure path.",
                            "locator": "tests/test_web_interface.py",
                            "commandId": "web-proof",
                            "expectedResult": "caller-visible failure behavior is observed",
                        }
                    ],
                    "releaseGateIds": ["release"],
                }
            )
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 5,
            "mode": "product",
            "commands": [
                {
                    "id": "web-proof",
                    "command": "python -m unittest tests.test_web_interface",
                    "purpose": "Exercise standalone Web interface endpoints.",
                }
            ],
            "releaseGates": [
                {
                    "id": "release",
                    "purpose": "Run standalone Web interface endpoint proof.",
                    "commandIds": ["web-proof"],
                }
            ],
            "requirements": requirements,
            "records": records,
        }

    def run_validator(
        self, contract: dict, evidence: dict
    ) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/web-interface.json", contract)
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_descriptor_adds_machine_contract_and_evidence_dependency(self) -> None:
        descriptor = json.loads(
            (COMPONENT / "component.json").read_text(encoding="utf-8")
        )
        self.assertEqual(descriptor["version"], 3)
        self.assertEqual(
            descriptor["requires"],
            ["capability.runtime", "lifecycle.implementation-evidence"],
        )
        registrations = descriptor["contract_registrations"]
        self.assertEqual(len(registrations), 1)
        self.assertEqual(registrations[0]["id"], "web_interface")
        self.assertEqual(
            registrations[0]["document"], "contracts/web-interface.json"
        )
        self.assertEqual(
            registrations[0]["schema"], "schemas/web-interface.schema.json"
        )

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.product_contract())

    def test_product_endpoints_require_browser_or_executable_proof_strength(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("endpoint coverage and proof strength: OK", result.stdout)

        weak_browser = self.run_validator(
            self.product_contract(),
            self.evidence(
                browser_proof_kind="inspection",
                browser_requirement_kind="end-to-end-test",
            ),
        )
        self.assertNotEqual(weak_browser.returncode, 0)
        self.assertIn("browser-level proof kind", weak_browser.stderr)
        self.assertIn(
            "static inspection or unit-only proof is insufficient",
            weak_browser.stderr,
        )

        weak_api = self.run_validator(
            self.product_contract(),
            self.evidence(
                api_proof_kind="unit-test",
                api_requirement_kind="integration-test",
            ),
        )
        self.assertNotEqual(weak_api.returncode, 0)
        self.assertIn("executable proof kind", weak_api.stderr)

    def test_browser_requirement_must_declare_browser_level_strength(self) -> None:
        result = self.run_validator(
            self.product_contract(),
            self.evidence(
                browser_proof_kind="end-to-end-test",
                browser_requirement_kind="inspection",
            ),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requiredPositiveProofKinds", result.stderr)
        self.assertIn("browser-level", result.stderr)

    def test_product_evidence_cannot_hide_selected_interface_in_template_mode(self) -> None:
        contract = json.loads(SEED.read_text(encoding="utf-8"))
        result = self.run_validator(contract, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "remains in template mode while product implementation evidence is active",
            result.stderr,
        )

    def test_unknown_or_duplicate_endpoint_targets_fail_closed(self) -> None:
        unknown = self.evidence()
        unknown["records"][0]["target"]["itemId"] = "other"
        result = self.run_validator(self.product_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing Web interface implementation-evidence target", result.stderr)
        self.assertIn("unknown Web interface implementation-evidence target", result.stderr)

        duplicate = self.evidence()
        second = deepcopy(duplicate["records"][0])
        second["id"] = "web-interface-endpoint-ui-duplicate"
        duplicate["records"].append(second)
        result = self.run_validator(self.product_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)

    def test_duplicate_method_path_endpoint_address_fails_closed(self) -> None:
        contract = self.product_contract()
        duplicate = deepcopy(contract["endpoints"][0])
        duplicate["id"] = "ui-alias"
        contract["endpoints"].append(duplicate)
        evidence = self.evidence()
        alias = deepcopy(evidence["records"][0])
        alias["id"] = "web-interface-endpoint-ui-alias"
        alias["target"]["itemId"] = "ui-alias"
        evidence["records"].append(alias)
        evidence["requirements"].append(
            {
                "id": "REQ-WEB-UI-ALIAS",
                "description": "The alias is caller-visible.",
                "recordIds": ["web-interface-endpoint-ui-alias"],
                "requiredPositiveProofKinds": ["end-to-end-test"],
            }
        )
        result = self.run_validator(contract, evidence)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate Web interface endpoint address: GET /ui", result.stderr)


if __name__ == "__main__":
    unittest.main()
