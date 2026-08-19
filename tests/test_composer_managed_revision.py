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

import composer_core as core


class ManagedSourceRevisionTests(unittest.TestCase):
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

    def test_update_advances_an_ancestor_lock_to_current_source_revision(self) -> None:
        current_revision = core.source_revision()
        parent_revision = core._run_git("rev-parse", "HEAD^").stdout.strip()
        self.assertNotEqual(parent_revision, current_revision)
        self.assertEqual(
            core._run_git(
                "merge-base",
                "--is-ancestor",
                parent_revision,
                current_revision,
                allow_failure=True,
            ).returncode,
            0,
        )

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
                "apply",
                "--mode",
                "initial",
                "--config",
                str(config_path),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)

            lock_path = target / core.LOCK_RELATIVE
            old_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            old_lock["source"]["revision"] = parent_revision
            lock_path.write_text(json.dumps(old_lock, indent=2) + "\n", encoding="utf-8")

            result, plan = self.run_composer(
                "plan",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(plan["from_revision"], parent_revision)
            self.assertEqual(plan["to_revision"], current_revision)
            self.assertEqual(plan["conflicts"], [])
            self.assertEqual(plan["files"]["create"], [])
            self.assertEqual(plan["files"]["replace"], [])
            self.assertEqual(plan["files"]["remove"], [])
            self.assertEqual(plan["lock_preview"]["source"]["revision"], current_revision)

            result, applied = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, applied)
            self.assertFalse(applied["no_op"])
            self.assertEqual(applied["from_revision"], parent_revision)
            self.assertEqual(applied["to_revision"], current_revision)
            self.assertEqual(
                json.loads(lock_path.read_text(encoding="utf-8"))["source"]["revision"],
                current_revision,
            )

            result, second = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, second)
            self.assertTrue(second["no_op"])


if __name__ == "__main__":
    unittest.main()
