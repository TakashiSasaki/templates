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
CLI_SCHEMA = (
    ROOT
    / "components"
    / "capability.cli"
    / "files"
    / "schemas"
    / "cli-interface.schema.json"
)


class HumanFirstWebappCliEvidenceTests(unittest.TestCase):
    def code_block_after(self, text: str, marker: str, language: str) -> str:
        marker_at = text.index(marker)
        opening = f"```{language}\n"
        start = text.index(opening, marker_at) + len(opening)
        end = text.index("\n```", start)
        return text[start:end]

    def test_walkthrough_makes_selected_cli_contract_and_executable_proof_explicit(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn("`contracts/cli-interface.json` | `seed`", text)
        contract = json.loads(
            self.code_block_after(
                text,
                "also replace the editable machine seed `contracts/cli-interface.json`",
                "json",
            )
        )
        schema = json.loads(CLI_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(contract)), [])
        self.assertEqual(contract["mode"], "product")
        self.assertEqual(contract["entrypoints"][0]["id"], "task-ledger")
        self.assertEqual(contract["entrypoints"][0]["versionArguments"], ["--version"])
        self.assertEqual(
            contract["entrypoints"][0]["structuredOutput"]["contractVersionField"],
            "contractVersion",
        )
        self.assertIn("cli_interface / entrypoint / task-ledger", text)
        self.assertIn("proof kind is `integration-test`", text)
        self.assertIn("invalid-argument exit code", text)
        self.assertIn("CLI contract left in `template` mode", text)
        self.assertIn('action="version", version="Task Ledger 1.0"', text)
        self.assertIn('self.assertEqual(invalid.returncode, 2)', text)

        japanese = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "`contracts/cli-interface.json` | `seed`",
            "`cli_interface / entrypoint / task-ledger`",
            "proof kind は `integration-test`",
            "invalid argument の exit code",
            'action="version", version="Task Ledger 1.0"',
            "self.assertEqual(invalid.returncode, 2)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, japanese)


if __name__ == "__main__":
    unittest.main()
