from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
LOCK_RELATIVE = Path(".template-composition/lock.json")


class ComposerPublicLifecycleAcceptanceTests(unittest.TestCase):
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

    def write_config(self, path: Path, *, include: list[str] | None = None) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {"include": include or [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def assert_valid(self, target: Path) -> None:
        result, payload = self.run_composer("validate", "--target", str(target))
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["errors"], [])

    def assert_managed_valid(self, target: Path) -> None:
        result, payload = self.run_composer("inspect", "--target", str(target))
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(payload["state"], "managed-valid")
        self.assertEqual(payload["errors"], [])

    def test_documented_happy_path_initial_update_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            initial_config = root / "initial.json"
            upgrade_config = root / "upgrade.json"
            self.write_config(initial_config)
            self.write_config(upgrade_config, include=["capability.cli"])

            result, payload = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["state"], "absent")

            result, plan = self.run_composer(
                "plan",
                "--config",
                str(initial_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(plan["operation"], "initial")
            self.assertFalse(target.exists(), "initial planning must remain read-only")

            result, applied = self.run_composer(
                "apply",
                "--config",
                str(initial_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, applied)
            self.assertTrue((target / LOCK_RELATIVE).is_file())
            self.assert_valid(target)
            self.assert_managed_valid(target)

            result, update_plan = self.run_composer(
                "plan",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, update_plan)
            self.assertEqual(update_plan["operation"], "update")
            self.assertEqual(update_plan["conflicts"], [])

            result, updated = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, updated)
            self.assertEqual(updated["status"], "updated")
            self.assertTrue(updated["no_op"])
            self.assert_valid(target)
            self.assert_managed_valid(target)

            result, upgrade_plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, upgrade_plan)
            self.assertEqual(upgrade_plan["operation"], "upgrade")
            self.assertEqual(upgrade_plan["conflicts"], [])
            self.assertEqual(
                upgrade_plan["components"]["added"],
                [
                    "capability.cli",
                    "capability.runtime",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                    "lifecycle.lifecycle-checkpoints",
                ],
            )

            result, upgraded = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, upgraded)
            self.assertEqual(upgraded["status"], "upgraded")
            self.assertFalse(upgraded["no_op"])
            self.assert_valid(target)
            self.assert_managed_valid(target)

            lock = json.loads((target / LOCK_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(lock["intent"]["components"]["include"], ["capability.cli"])


if __name__ == "__main__":
    unittest.main()
