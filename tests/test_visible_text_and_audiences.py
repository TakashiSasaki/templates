from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class VisibleTextAndAudienceTests(unittest.TestCase):
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

    def test_schema_rejects_common_invisible_only_text(self) -> None:
        invisible_values = (
            "\x00",
            "\u034f",
            "\u200b",
            "\u2060",
            "\u2800",
            "\u3164",
            "\ufe0f",
            " \u200b\t",
        )

        for contract_name, path in self.text_cases:
            for invisible_value in invisible_values:
                with self.subTest(
                    contract=contract_name,
                    path=path,
                    value=repr(invisible_value),
                ):
                    document = copy.deepcopy(self.documents[contract_name])
                    self.set_nested(document, path, invisible_value)
                    self.assertFalse(self.validators[contract_name].is_valid(document))

    def test_repository_validation_rejects_invisible_text_not_captured_by_categories(self) -> None:
        for invisible_value in ("\u0301", "\u2800"):
            for contract_name, path in self.text_cases:
                with self.subTest(
                    contract=contract_name,
                    path=path,
                    value=repr(invisible_value),
                ):
                    documents = copy.deepcopy(self.documents)
                    self.set_nested(documents[contract_name], path, invisible_value)
                    errors = validate_contracts.cross_validate(documents)
                    self.assertTrue(
                        any("must contain at least one visible character" in error for error in errors)
                    )

    def test_visible_unicode_text_remains_valid(self) -> None:
        for contract_name, path in self.text_cases:
            with self.subTest(contract=contract_name, path=path):
                document = copy.deepcopy(self.documents[contract_name])
                self.set_nested(document, path, "  利用者に表示する説明  ")
                self.assertTrue(self.validators[contract_name].is_valid(document))

    def test_required_authentication_rejects_anonymous_audience(self) -> None:
        surface_document = copy.deepcopy(self.documents["surfaces"])
        surface_document["surfaces"][1]["audiences"].append("anonymous")
        self.assertFalse(self.validators["surfaces"].is_valid(surface_document))

        documents = copy.deepcopy(self.documents)
        documents["surfaces"]["surfaces"][1]["audiences"].append("anonymous")
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(
            any(
                "required authentication must not include anonymous audience" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
