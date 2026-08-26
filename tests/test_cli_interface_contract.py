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
COMPONENT = ROOT / "components" / "capability.cli"
SCHEMA = COMPONENT / "files" / "schemas" / "cli-interface.schema.json"
SEED = COMPONENT / "files" / "contracts" / "cli-interface.json"
VALIDATOR = (
    COMPONENT
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_cli_interface.py"
)


class CliInterfaceContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def product_contract(self) -> dict:
        return {
            "$schema": "../schemas/cli-interface.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "entrypoints": [
                {
                    "id": "main",
                    "command": ["python", "-m", "field_log"],
                    "workingDirectory": ".",
                    "helpArguments": ["--help"],
                    "versionArguments": ["--version"],
                    "structuredOutput": {
                        "arguments": ["list", "--format", "json"],
                        "format": "json",
                        "contractVersionField": "contractVersion",
                    },
                    "exitCodes": {
                        "success": 0,
                        "negativeResult": 1,
                        "invalidInput": 2,
                        "unavailable": 3,
                        "refused": 4,
                        "internalFailure": 5,
                        "additionalInputRequired": 6,
                    },
                }
            ],
        }

    def evidence(
        self,
        *,
        proof_kind: str = "integration-test",
        requirement_kind: str | None = None,
    ) -> dict:
        required_kind = requirement_kind or proof_kind
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 3,
            "mode": "product",
            "commands": [
                {
                    "id": "cli-proof",
                    "command": "python -m unittest tests.test_cli",
                    "purpose": (
                        "Exercise the packaged CLI through its public command boundary."
                    ),
                }
            ],
            "releaseGates": [
                {
                    "id": "release",
                    "purpose": "Run executable CLI proof.",
                    "commandIds": ["cli-proof"],
                }
            ],
            "requirements": [
                {
                    "id": "REQ-CLI-MAIN",
                    "description": "The packaged CLI entrypoint executes for callers.",
                    "recordIds": ["cli-interface-entrypoint-main"],
                    "requiredPositiveProofKinds": [required_kind],
                }
            ],
            "records": [
                {
                    "id": "cli-interface-entrypoint-main",
                    "target": {
                        "kind": "contract-item",
                        "contractId": "cli_interface",
                        "itemKind": "entrypoint",
                        "itemId": "main",
                    },
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "Packaged CLI adapter.",
                        "locator": "field_log/__main__.py",
                    },
                    "positiveEvidence": [
                        {
                            "id": "cli-positive",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": "Execute a valid CLI invocation.",
                            "locator": "tests/test_cli.py",
                            "commandId": "cli-proof",
                            "expectedResult": (
                                "exit 0 and expected structured result"
                            ),
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": "cli-negative",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": "Execute an invalid CLI invocation.",
                            "locator": "tests/test_cli.py",
                            "commandId": "cli-proof",
                            "expectedResult": (
                                "documented non-zero exit and stderr diagnostic"
                            ),
                        }
                    ],
                    "releaseGateIds": ["release"],
                }
            ],
        }

    def run_validator(
        self, contract: dict, evidence: dict
    ) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/cli-interface.json", contract)
        self.write_json(
            root / "contracts/implementation-evidence.json", evidence
        )
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.product_contract())

    def test_product_cli_requires_executable_positive_negative_and_requirement_strength(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("executable evidence strength: OK", result.stdout)

        weak_proof = self.run_validator(
            self.product_contract(),
            self.evidence(
                proof_kind="inspection",
                requirement_kind="integration-test",
            ),
        )
        self.assertNotEqual(weak_proof.returncode, 0)
        self.assertIn("executable proof kind", weak_proof.stderr)
        self.assertIn(
            "static inspection or unit-only proof is insufficient",
            weak_proof.stderr,
        )

        weak_requirement = self.run_validator(
            self.product_contract(),
            self.evidence(
                proof_kind="integration-test",
                requirement_kind="inspection",
            ),
        )
        self.assertNotEqual(weak_requirement.returncode, 0)
        self.assertIn("requiredPositiveProofKinds", weak_requirement.stderr)

    def test_product_evidence_cannot_hide_selected_cli_in_template_mode(self) -> None:
        contract = json.loads(SEED.read_text(encoding="utf-8"))
        result = self.run_validator(contract, self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "remains in template mode while product implementation evidence is active",
            result.stderr,
        )

    def test_unknown_or_duplicate_cli_entrypoint_targets_fail_closed(self) -> None:
        evidence = self.evidence()
        unknown = deepcopy(evidence)
        unknown["records"][0]["target"]["itemId"] = "other"
        result = self.run_validator(self.product_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing CLI implementation-evidence target", result.stderr)
        self.assertIn("unknown CLI implementation-evidence target", result.stderr)

        duplicate = deepcopy(evidence)
        second = deepcopy(duplicate["records"][0])
        second["id"] = "cli-interface-entrypoint-main-duplicate"
        duplicate["records"].append(second)
        result = self.run_validator(self.product_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)


if __name__ == "__main__":
    unittest.main()
