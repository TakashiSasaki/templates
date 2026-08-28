from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "components/artifact.webapp-core"
WEBAPP_FILES = WEBAPP / "files"
ACTION_REGISTRY = WEBAPP_FILES / ".template-composition/webapp-actions.json"
ACTION_SCHEMA = WEBAPP_FILES / ".template-composition/webapp-actions.schema.json"
DIAGNOSTIC_SCHEMA = WEBAPP_FILES / ".template-composition/browser-proof-diagnostics.schema.json"
DIAGNOSTIC_SCRIPT = WEBAPP_FILES / "scripts/browser_prerequisite_diagnostics.py"
RUN_ACTION = ROOT / "components/lifecycle.composition-state/files/.template-composition/run_action.py"


class BrowserPrerequisiteActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(ACTION_REGISTRY.read_text(encoding="utf-8"))
        cls.action_schema = json.loads(ACTION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.action_schema)
        cls.action_validator = Draft202012Validator(cls.action_schema)
        cls.action_validator.validate(cls.registry)

        cls.diagnostic_schema = json.loads(DIAGNOSTIC_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.diagnostic_schema)
        cls.diagnostic_validator = Draft202012Validator(cls.diagnostic_schema)

    def test_component_materializes_action_contract(self) -> None:
        component = json.loads((WEBAPP / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(component["version"], 14)
        materials = {
            entry["destination"]: entry["ownership"]
            for entry in component["materials"]
        }
        self.assertEqual(materials[".template-composition/webapp-actions.json"], "managed")
        self.assertEqual(materials[".template-composition/webapp-actions.schema.json"], "managed")
        self.assertEqual(materials["scripts/browser_prerequisite_diagnostics.py"], "managed")
        self.assertEqual(materials[".template-composition/browser-proof-diagnostics.schema.json"], "managed")

    def test_public_action_argv_is_exact_and_rejects_interpreter_augmentation(self) -> None:
        action = self.registry["actions"]["diagnose-browser-prerequisites"]
        self.assertEqual(
            action,
            {
                "argv": [
                    "{python}",
                    ".template-composition/run_action.py",
                    "diagnose-browser-prerequisites",
                    "--browser-binary",
                    "{browser_binary}",
                    "--webdriver",
                    "{webdriver}",
                    "--compatibility",
                    "{compatibility}",
                    "--localhost",
                    "{localhost}",
                ],
                "caller_inputs": [
                    "{python}",
                    "{browser_binary}",
                    "{webdriver}",
                    "{compatibility}",
                    "{localhost}",
                ],
                "output_schema": ".template-composition/browser-proof-diagnostics.schema.json",
            },
        )
        mutated = json.loads(json.dumps(self.registry))
        mutated["actions"]["diagnose-browser-prerequisites"]["argv"].insert(1, "-I")
        with self.assertRaises(ValidationError):
            self.action_validator.validate(mutated)

    def _run_materialized(self, observations: list[str]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".template-composition").mkdir()
            (root / "scripts").mkdir()
            shutil.copy2(RUN_ACTION, root / ".template-composition/run_action.py")
            shutil.copy2(DIAGNOSTIC_SCRIPT, root / "scripts/browser_prerequisite_diagnostics.py")
            return subprocess.run(
                [
                    sys.executable,
                    str(root / ".template-composition/run_action.py"),
                    "diagnose-browser-prerequisites",
                    *observations,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_dispatcher_executes_provider_and_output_schema(self) -> None:
        result = self._run_materialized(
            [
                "--browser-binary", "available",
                "--webdriver", "available",
                "--compatibility", "compatible",
                "--localhost", "allowed",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.diagnostic_validator.validate(payload)
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["release_impact"], "none")
        self.assertEqual(payload["missing_or_blocked_prerequisites"], [])

    def test_dispatcher_preserves_fail_closed_blocker_classification(self) -> None:
        result = self._run_materialized(
            [
                "--browser-binary", "available",
                "--webdriver", "unavailable",
                "--compatibility", "not-checked",
                "--localhost", "restricted",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.diagnostic_validator.validate(payload)
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["release_impact"], "not-ready")
        self.assertEqual(
            payload["missing_or_blocked_prerequisites"],
            ["webdriver-unavailable", "localhost-browser-sandbox-restricted"],
        )

    def test_dispatcher_rejects_reconstructed_or_invalid_arguments(self) -> None:
        wrong_order = self._run_materialized(
            [
                "--webdriver", "available",
                "--browser-binary", "available",
                "--compatibility", "compatible",
                "--localhost", "allowed",
            ]
        )
        self.assertEqual(wrong_order.returncode, 2)
        self.assertIn("must use --browser-binary", wrong_order.stderr)

        invalid_value = self._run_materialized(
            [
                "--browser-binary", "maybe",
                "--webdriver", "available",
                "--compatibility", "compatible",
                "--localhost", "allowed",
            ]
        )
        self.assertEqual(invalid_value.returncode, 2)
        self.assertIn("unsupported value", invalid_value.stderr)


if __name__ == "__main__":
    unittest.main()
