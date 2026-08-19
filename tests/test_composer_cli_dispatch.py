from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


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


if __name__ == "__main__":
    unittest.main()
