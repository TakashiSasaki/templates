from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPOSER = SCRIPTS / "compose.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_managed as managed


class ComposerDispatchTests(unittest.TestCase):
    def run_composer(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"composer did not emit JSON: {exc}\n{result.stdout}\n{result.stderr}")
        return result, payload

    def test_top_level_help_exposes_public_lifecycle_and_mode_config_rules(self) -> None:
        for help_flag in ("--help", "-h"):
            with self.subTest(help_flag=help_flag):
                result = subprocess.run(
                    [sys.executable, str(COMPOSER), help_flag],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("inspect -> plan -> apply -> validate", result.stdout)
                self.assertIn("initial", result.stdout)
                self.assertIn("update", result.stdout)
                self.assertIn("upgrade", result.stdout)
                self.assertIn("--config is required", result.stdout)
                self.assertIn("--config is forbidden", result.stdout)
                self.assertIn("Interrupted update and upgrade recovery", result.stdout)
                self.assertIn("both omit --config", result.stdout)
                self.assertIn("docs/consumer-guide.md", result.stdout)
                self.assertIn("docs/reference/composer.md", result.stdout)

    def test_managed_planner_module_has_no_standalone_cli(self) -> None:
        self.assertTrue(callable(managed.plan_update))
        self.assertFalse(hasattr(managed, "command_apply_update"))
        self.assertFalse(hasattr(managed, "main"))

    def test_flag_first_initial_and_update_dispatch_match_command_first_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "composition.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipe": "skill",
                        "components": {"include": [], "exclude": []},
                        "parameters": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            target = root / "consumer"

            result, payload = self.run_composer(
                "--mode",
                "initial",
                "plan",
                "--config",
                str(config_path),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["operation"], "initial")

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "initial",
                "--config",
                str(config_path),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)

            result, payload = self.run_composer(
                "--mode",
                "update",
                "plan",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["operation"], "update")

            result, payload = self.run_composer(
                "--mode=update",
                "apply",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "updated")
            self.assertTrue(payload["no_op"])

    def test_missing_managed_lock_has_same_error_for_plan_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "unmanaged"
            for command in ("plan", "apply"):
                result, payload = self.run_composer(
                    command,
                    "--mode",
                    "update",
                    "--target",
                    str(target),
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["code"], "MANAGED_LOCK_REQUIRED")
                self.assertIn("Run `inspect`", payload["message"])
                self.assertIn("use initial mode only when the target is unmanaged", payload["message"])


if __name__ == "__main__":
    unittest.main()
