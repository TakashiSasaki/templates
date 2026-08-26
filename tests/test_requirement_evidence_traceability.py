from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
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
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "field_log_requirement_evidence"

if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SPEC = importlib.util.spec_from_file_location("implementation_evidence_validator", VALIDATOR)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load_fixture(name: str) -> dict:
    value = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("fixture must contain a JSON object")
    return value


def validate_document(document: dict) -> list[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        contracts = root / "contracts"
        contracts.mkdir()
        manifest = {
            "contracts": [
                {
                    "id": "field_log",
                    "versionHistory": [{"version": 1}],
                }
            ]
        }
        (contracts / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (contracts / "implementation-evidence.json").write_text(
            json.dumps(document), encoding="utf-8"
        )
        return validator.validate(root)


class RequirementEvidenceTraceabilityTests(unittest.TestCase):
    def test_field_log_missing_browser_filter_proof_is_orphaned(self) -> None:
        document = load_fixture("browser-filter-missing.json")
        errors = validate_document(document)
        self.assertIn(
            "orphan product requirement without evidence record: "
            "REQ-SEVERITY-BROWSER-FILTER",
            errors,
        )
        self.assertNotIn(
            "orphan product requirement without evidence record: REQ-SEVERITY-API",
            errors,
        )
        self.assertNotIn(
            "orphan product requirement without evidence record: "
            "REQ-SEVERITY-CLI-FILTER",
            errors,
        )

    def test_field_log_browser_filter_proof_closes_requirement_graph(self) -> None:
        document = load_fixture("browser-filter-proven.json")
        self.assertEqual(validate_document(document), [])

    def test_unknown_requirement_reference_is_rejected(self) -> None:
        document = load_fixture("browser-filter-proven.json")
        document["records"][0]["requirementIds"] = ["REQ-UNKNOWN"]
        errors = validate_document(document)
        self.assertIn(
            "record severity-api: unknown product requirement REQ-UNKNOWN",
            errors,
        )
        self.assertIn(
            "orphan product requirement without evidence record: REQ-SEVERITY-API",
            errors,
        )

    def test_duplicate_requirement_ids_are_rejected_semantically(self) -> None:
        document = load_fixture("browser-filter-proven.json")
        duplicate = copy.deepcopy(document["requirements"][0])
        duplicate["description"] = "A conflicting duplicate requirement description."
        document["requirements"].append(duplicate)
        errors = validate_document(document)
        self.assertIn(
            "duplicate implementation-evidence requirement id: REQ-SEVERITY-API",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
