from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ImplementationEvidenceNegativeRequirementTests(unittest.TestCase):
    def test_every_target_requires_negative_evidence_in_template_mode(self) -> None:
        document = validate_contracts.load_json(
            ROOT / "contracts/implementation-evidence.json"
        )
        schema = validate_contracts.load_json(
            ROOT / "schemas/implementation-evidence.schema.json"
        )
        document = copy.deepcopy(document)
        record = next(
            record
            for record in document["records"]
            if record["target"] == {"kind": "route", "id": "application-home"}
        )
        record["negativeEvidence"] = []

        self.assertFalse(Draft202012Validator(schema).is_valid(document))

    def test_every_target_requires_negative_evidence_in_product_mode(self) -> None:
        document = validate_contracts.load_json(
            ROOT / "contracts/implementation-evidence.json"
        )
        schema = validate_contracts.load_json(
            ROOT / "schemas/implementation-evidence.schema.json"
        )
        document = copy.deepcopy(document)
        document["mode"] = "product"
        record = next(
            record
            for record in document["records"]
            if record["target"] == {"kind": "viewport", "id": "compact"}
        )
        record["negativeEvidence"] = []

        self.assertFalse(Draft202012Validator(schema).is_valid(document))


if __name__ == "__main__":
    unittest.main()
