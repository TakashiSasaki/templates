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


class ComposerPostApplyGuidanceTests(unittest.TestCase):
    def write_config(
        self,
        root: Path,
        name: str,
        *,
        include: list[str],
    ) -> Path:
        path = root / name
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {"include": include, "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def run_composer(
        self, *arguments: str
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
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
            self.fail(
                f"composer did not emit JSON: {exc}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        self.assertIsInstance(payload, dict)
        return result, payload

    def expected_active_ownership(self, target: Path) -> dict:
        lock = json.loads((target / LOCK_RELATIVE).read_text(encoding="utf-8"))
        return {
            "composition_owned": {
                "managed": sorted(
                    entry["destination"]
                    for entry in lock["files"]
                    if entry["ownership"] == "managed"
                ),
                "generated": sorted(
                    entry["destination"]
                    for entry in lock["files"]
                    if entry["ownership"] == "generated"
                ),
            },
            "consumer_owned": {
                "seeds": sorted(
                    entry["destination"]
                    for entry in lock["files"]
                    if entry["ownership"] == "seed"
                ),
                "extras": [],
            },
        }

    def test_initial_and_update_report_lock_derived_active_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = self.write_config(root, "skill.json", include=[])

            result, initial = self.run_composer(
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, initial)
            self.assertEqual(initial["ownership"], self.expected_active_ownership(target))
            initial_steps = [entry["id"] for entry in initial["next_steps"]]
            self.assertIn("respect-composition-ownership", initial_steps)
            self.assertIn("edit-consumer-owned-seeds", initial_steps)
            self.assertNotIn("review-consumer-owned-extras", initial_steps)
            self.assertEqual(initial_steps[-1], "validate")

            result, updated = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, updated)
            self.assertTrue(updated["no_op"])
            self.assertEqual(updated["ownership"], self.expected_active_ownership(target))
            self.assertEqual(updated["ownership"]["consumer_owned"]["extras"], [])
            self.assertEqual(updated["next_steps"][-1]["id"], "validate")

    def test_upgrade_reports_removed_seeds_as_consumer_owned_extras(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            initial_config = self.write_config(
                root,
                "with-cli.json",
                include=["capability.cli"],
            )
            result, initial = self.run_composer(
                "apply",
                "--config",
                str(initial_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, initial)
            self.assertTrue((target / "CLI_INTERFACE.md").is_file())
            self.assertTrue((target / "RUNTIME.md").is_file())

            upgrade_config = self.write_config(root, "minimal.json", include=[])
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
            self.assertEqual(
                upgraded["ownership"]["consumer_owned"]["extras"],
                ["CLI_INTERFACE.md", "RUNTIME.md"],
            )
            self.assertTrue((target / "CLI_INTERFACE.md").is_file())
            self.assertTrue((target / "RUNTIME.md").is_file())

            lock = json.loads((target / LOCK_RELATIVE).read_text(encoding="utf-8"))
            locked_destinations = {entry["destination"] for entry in lock["files"]}
            self.assertNotIn("CLI_INTERFACE.md", locked_destinations)
            self.assertNotIn("RUNTIME.md", locked_destinations)
            self.assertFalse((target / "docs/runtime-selection.md").exists())

            step_ids = [entry["id"] for entry in upgraded["next_steps"]]
            self.assertIn("review-consumer-owned-extras", step_ids)
            self.assertEqual(step_ids[-1], "validate")


if __name__ == "__main__":
    unittest.main()
