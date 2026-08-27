from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "components/artifact.webapp-core/files/scripts/browser_prerequisite_diagnostics.py"
SCHEMA = ROOT / "components/artifact.webapp-core/files/schemas/browser-proof-diagnostics.schema.json"

SPEC = importlib.util.spec_from_file_location("browser_prerequisite_diagnostics", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load browser prerequisite diagnostics")
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


class BrowserPrerequisiteDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)

    def assert_valid(self, value: dict) -> None:
        self.validator.validate(value)

    def test_available_prerequisites_have_no_release_blocker(self) -> None:
        value = diagnostics.diagnose(
            browser_binary="available",
            webdriver="available",
            compatibility="compatible",
            localhost="allowed",
        )
        self.assert_valid(value)
        self.assertEqual(value["status"], "available")
        self.assertEqual(value["missing_or_blocked_prerequisites"], [])
        self.assertEqual(value["release_impact"], "none")

    def test_each_blocker_is_machine_distinguishable_and_not_ready(self) -> None:
        value = diagnostics.diagnose(
            browser_binary="unavailable",
            webdriver="unavailable",
            compatibility="incompatible",
            localhost="restricted",
        )
        self.assert_valid(value)
        self.assertEqual(
            value["missing_or_blocked_prerequisites"],
            [
                "browser-binary-unavailable",
                "webdriver-unavailable",
                "incompatible-browser-driver",
                "localhost-browser-sandbox-restricted",
            ],
        )
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["release_impact"], "not-ready")

    def test_unchecked_prerequisites_are_not_claimed_available(self) -> None:
        value = diagnostics.diagnose()
        self.assert_valid(value)
        self.assertEqual(value["status"], "not-checked")
        self.assertEqual(value["missing_or_blocked_prerequisites"], [])
        self.assertEqual(value["release_impact"], "not-evaluated")


if __name__ == "__main__":
    unittest.main()
