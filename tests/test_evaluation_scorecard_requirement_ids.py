from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "examples/evaluations/evaluation-scorecard.schema.json"


class EvaluationScorecardRequirementIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        item_schema = schema["properties"]["staged_change_chronology"]["properties"][
            "added_requirement_ids"
        ]["items"]
        cls.validator = Draft202012Validator(item_schema)

    def test_staged_change_requirement_ids_use_canonical_req_pattern(self) -> None:
        for valid_id in ("REQ-CHANGE-ONE", "REQ-1", "REQ-A1-B2"):
            with self.subTest(valid_id=valid_id):
                self.validator.validate(valid_id)

        for invalid_id in (
            "req-lowercase",
            "CHANGE-1",
            "REQ_INVALID_CHAR",
            "REQ-",
            "REQ-A-",
            "REQ--A",
            "REQ-A--B",
        ):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid_id)


if __name__ == "__main__":
    unittest.main()
