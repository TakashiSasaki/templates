from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
WALKTHROUGH_JA = (
    ROOT / "translations" / "ja" / "docs" / "guides" / "webapp-product-walkthrough.md"
)
SERVICE_SCHEMA = (
    ROOT
    / "components"
    / "capability.service"
    / "files"
    / "schemas"
    / "service-interface.schema.json"
)


class HumanFirstWebappServiceEvidenceTests(unittest.TestCase):
    def code_block_after(self, text: str, marker: str, language: str) -> str:
        marker_at = text.index(marker)
        opening = f"```{language}\n"
        start = text.index(opening, marker_at) + len(opening)
        end = text.index("\n```", start)
        return text[start:end]

    def test_walkthrough_makes_selected_service_contract_and_operation_proof_explicit(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        contract = json.loads(
            self.code_block_after(
                text,
                "replace the editable machine seed `contracts/service-interface.json`",
                "json",
            )
        )
        schema = json.loads(SERVICE_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(contract)), [])
        self.assertEqual(contract["mode"], "product")
        self.assertEqual(contract["protocol"], "http-json")
        self.assertEqual(
            {operation["id"] for operation in contract["operations"]},
            {
                "list-tasks",
                "get-task",
                "create-task",
                "update-task",
                "delete-task",
                "health",
            },
        )
        self.assertIn("service_interface/operation/<id>", text)
        self.assertIn("positive/negative proof locator", text)
        self.assertIn("all six operations", text)
        for snippet in (
            'request("POST", "/api/tasks", {"title": ""})',
            'request("GET", "/api/tasks/999999")',
            'request("PATCH", "/api/tasks/999999", {"completed": True})',
            'request("DELETE", f"/api/tasks/{created[\'id\']}")',
            'request("GET", "/not-a-service-route")',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

        japanese = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "`contracts/service-interface.json`",
            "`contract-item / service_interface / operation / <id>`",
            "proof kind は `integration-test`",
            "6 operationすべて",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, japanese)


if __name__ == "__main__":
    unittest.main()
