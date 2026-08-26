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
EXAMPLE = ROOT / "examples/onboarding/task-ledger/implementation-evidence.example.json"
SCHEMA = ROOT / "components/lifecycle.implementation-evidence/files/schemas/implementation-evidence.schema.json"
VALIDATOR_PATH = (
    ROOT
    / "components/lifecycle.implementation-evidence"
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
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SPEC = importlib.util.spec_from_file_location("task_ledger_example_validator", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation-evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class TaskLedgerEvidenceExampleTests(unittest.TestCase):
    def test_example_is_schema_and_semantically_valid(self) -> None:
        value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(value)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contracts = root / "contracts"
            contracts.mkdir()
            (contracts / "manifest.json").write_text(
                json.dumps({
                    "contracts": [{
                        "id": "routes",
                        "versionHistory": [{"version": 1}],
                    }]
                }),
                encoding="utf-8",
            )
            (contracts / "implementation-evidence.json").write_text(
                json.dumps(value), encoding="utf-8"
            )
            self.assertEqual(validator.validate(root), [])
            self.assertEqual(validator.release_readiness_errors(value), [])


if __name__ == "__main__":
    unittest.main()
