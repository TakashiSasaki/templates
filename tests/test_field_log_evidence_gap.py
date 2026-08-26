from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / "schemas"
    / "implementation-evidence.schema.json"
)
VALIDATOR_PATH = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_implementation_evidence.py"
)
COMMON_DIR = (
    ROOT
    / "components"
    / "lifecycle.contract-evolution"
    / "files"
    / ".template-composition"
    / "validators"
)
WEBAPP_SCRIPTS = (
    ROOT / "components" / "artifact.webapp-core" / "files" / "scripts"
)
for path in (COMMON_DIR, WEBAPP_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("field_log_evidence_gap_validator", VALIDATOR_PATH)
webapp = load_module(
    "field_log_webapp_evidence_validator",
    WEBAPP_SCRIPTS / "validate_webapp_evidence.py",
)


def field_log_evidence(
    proof_kind: str = "integration-test",
    proof_status: str = "verified",
    *,
    capabilities: list[str] | None = None,
) -> dict:
    return {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 6,
        "mode": "product",
        "commands": [
            {
                "id": "field-log-proof",
                "command": "python tests/test_field_log.py",
                "purpose": "Exercise the Field Log product proof.",
                "execution": {
                    "capabilities": capabilities or ["integration"],
                    "harness": {
                        "kind": "repository-file",
                        "locator": "tests/test_field_log.py",
                    },
                    "supportsNegativePath": True,
                },
            }
        ],
        "releaseGates": [
            {
                "id": "field-log-release",
                "purpose": "Require Field Log product proof.",
                "commandIds": ["field-log-proof"],
            }
        ],
        "requirements": [
            {
                "id": "REQ-SEVERITY-BROWSER-FILTER",
                "description": (
                    "Field Log browser UI filters entries by severity; "
                    "API, CLI, and edit UI coverage is not browser proof."
                ),
                "recordIds": ["field-log-severity-filter"],
                "requiredPositiveProofKinds": [
                    "end-to-end-test",
                    "accessibility-test",
                ],
            }
        ],
        "records": [
            {
                "id": "field-log-severity-filter",
                "target": {
                    "kind": "contract-item",
                    "contractId": "surfaces",
                    "itemKind": "surface",
                    "itemId": "main",
                },
                "implementationBoundary": {
                    "status": "verified",
                    "description": "The Field Log severity-filter boundary exists.",
                    "locator": "app/filter.py",
                },
                "positiveEvidence": [
                    {
                        "id": "field-log-severity-positive",
                        "status": proof_status,
                        "kind": proof_kind,
                        "description": "The selected severity is reflected in browser-visible entries.",
                        "locator": "tests/test_field_log.py",
                        "commandId": "field-log-proof",
                        "expectedResult": "Only entries of the selected severity are visible.",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "field-log-severity-negative",
                        "status": proof_status,
                        "kind": proof_kind,
                        "description": "An unsupported severity filter is rejected.",
                        "locator": "tests/test_field_log.py",
                        "commandId": "field-log-proof",
                        "expectedResult": "Unsupported severity input is rejected.",
                    }
                ],
                "releaseGateIds": ["field-log-release"],
            }
        ],
    }


class FieldLogEvidenceGapTests(unittest.TestCase):
    def write_fixture(self, root: Path, value: dict) -> None:
        contracts = root / "contracts"
        contracts.mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "app").mkdir()
        (root / "tests" / "test_field_log.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        (root / "app" / "filter.py").write_text(
            "# Field Log filter boundary\n", encoding="utf-8"
        )
        (contracts / "manifest.json").write_text(
            json.dumps(
                {
                    "contracts": [
                        {
                            "id": "surfaces",
                            "versionHistory": [{"version": 1}],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (contracts / "implementation-evidence.json").write_text(
            json.dumps(value), encoding="utf-8"
        )

    def test_schema_can_pass_while_missing_required_proof_kind_blocks_product_evidence(self) -> None:
        value = field_log_evidence()
        Draft202012Validator(
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        ).validate(value)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            errors = validator.validate(root)
            blockers = validator.release_readiness_errors(value)
        self.assertTrue(any("required kind" in error for error in errors), errors)
        self.assertTrue(
            any("required kind" in blocker for blocker in blockers),
            blockers,
        )

    def test_end_to_end_label_without_browser_execution_still_fails_field_log_browser_proof(self) -> None:
        value = field_log_evidence(
            proof_kind="end-to-end-test",
            capabilities=["end-to-end"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])
        browser_errors = webapp.browser_level_proof_errors(value)
        self.assertTrue(
            any("browser execution capability" in error for error in browser_errors),
            browser_errors,
        )

    def test_real_browser_capability_closes_the_field_log_gap(self) -> None:
        value = field_log_evidence(
            proof_kind="end-to-end-test",
            capabilities=["end-to-end", "browser"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_fixture(root, value)
            self.assertEqual(validator.validate(root), [])
        self.assertEqual(webapp.browser_level_proof_errors(value), [])
        self.assertEqual(validator.release_readiness_errors(value), [])


if __name__ == "__main__":
    unittest.main()
