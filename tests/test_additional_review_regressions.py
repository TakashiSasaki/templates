from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class AdditionalReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.validators = {
            name: Draft202012Validator(validate_contracts.load_json(ROOT / schema_path))
            for name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items()
        }
        self.text_cases = (
            ("surfaces", ("surfaces", 0, "title")),
            ("surfaces", ("surfaces", 0, "purpose")),
            ("routes", ("routes", 0, "accessibility", "focusTarget")),
            ("ui_states", ("states", 0, "description")),
            ("ui_states", ("states", 0, "focusStrategy")),
            ("viewports", ("viewports", 0, "description")),
        )

    @staticmethod
    def set_nested(document: Any, path: tuple[str | int, ...], value: Any) -> None:
        target = document
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

    def assert_rejected_as_invisible(self, invalid_value: str) -> None:
        for contract_name, path in self.text_cases:
            with self.subTest(
                contract=contract_name,
                path=path,
                value=repr(invalid_value),
            ):
                document = copy.deepcopy(self.documents[contract_name])
                self.set_nested(document, path, invalid_value)
                self.assertFalse(self.validators[contract_name].is_valid(document))

                documents = copy.deepcopy(self.documents)
                self.set_nested(documents[contract_name], path, invalid_value)
                errors = validate_contracts.cross_validate(documents)
                self.assertTrue(
                    any("must contain at least one visible character" in error for error in errors)
                )

    def test_null_notehead_is_not_visible_text(self) -> None:
        for invalid_value in ("\U0001D159", " \U0001D159\t"):
            self.assert_rejected_as_invisible(invalid_value)

    def test_egyptian_hieroglyph_blanks_are_not_visible_text(self) -> None:
        for blank_character in ("\U00013441", "\U00013442"):
            for invalid_value in (blank_character, f" {blank_character}\t"):
                self.assert_rejected_as_invisible(invalid_value)

    def test_invalid_utf8_is_reported_for_contracts_and_schemas(self) -> None:
        cases = (
            ("contracts/routes.json", "contracts/routes.json"),
            ("schemas/routes.schema.json", "schemas/routes.schema.json"),
        )
        for relative_path, expected_path in cases:
            with self.subTest(path=relative_path):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    temporary_root = Path(temporary_directory)
                    shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
                    shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
                    (temporary_root / relative_path).write_bytes(b"\xff")
                    errors = validate_contracts.validate_repository(temporary_root)
                self.assertTrue(
                    any(
                        error.startswith(f"{expected_path}: unable to load JSON:")
                        and "invalid start byte" in error
                        for error in errors
                    )
                )


if __name__ == "__main__":
    unittest.main()
