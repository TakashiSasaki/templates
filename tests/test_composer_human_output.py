from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from composer_human_output import render_human


class ComposerHumanOutputTests(unittest.TestCase):
    def run_composer(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_skill_config(self, path: Path) -> None:
        path.write_text(
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

    def test_default_output_remains_identical_to_explicit_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "absent"
            default = self.run_composer("inspect", "--target", str(target))
            explicit = self.run_composer(
                "inspect",
                "--target",
                str(target),
                "--format",
                "json",
            )
            self.assertEqual(default.returncode, 0, default.stderr)
            self.assertEqual(explicit.returncode, 0, explicit.stderr)
            self.assertEqual(default.stdout, explicit.stdout)
            payload = json.loads(default.stdout)
            self.assertEqual(payload["state"], "absent")

    def test_human_inspect_reports_state_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "absent"
            result = self.run_composer(
                "--format",
                "human",
                "inspect",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Composition inspect", result.stdout)
            self.assertIn("State: absent", result.stdout)
            self.assertIn("Next:", result.stdout)
            with self.assertRaises(json.JSONDecodeError):
                json.loads(result.stdout)

    def test_human_plan_states_read_only_boundary_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_skill_config(config)
            result = self.run_composer(
                "plan",
                "--config",
                str(config),
                "--target",
                str(target),
                "--format=human",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Composition plan", result.stdout)
            self.assertIn("Operation: initial", result.stdout)
            self.assertIn("plan is read-only", result.stdout)
            self.assertIn("Conflicts: 0", result.stdout)
            self.assertIn("run apply with the same mode, config, and target", result.stdout)
            self.assertFalse(target.exists(), "human presentation must not mutate a plan")

    def test_managed_plan_summarizes_structured_file_and_component_changes(self) -> None:
        text = render_human(
            {
                "operation": "update",
                "files": {
                    "create": [{"destination": "new.txt"}],
                    "replace": [{"destination": "managed.txt"}],
                    "remove": [{"destination": "old.txt"}],
                    "preserve": [],
                    "unchanged": [],
                    "conflict": [],
                },
                "components": {
                    "added": ["capability.new"],
                    "removed": [],
                    "changed": [{"id": "artifact.skill-core"}],
                    "unchanged": [],
                },
                "conflicts": [],
            },
            "plan",
        )
        self.assertIn("File mutations: 3 total (1 create, 1 replace, 1 remove).", text)
        self.assertIn("Component transitions: 2 total (1 added, 0 removed, 1 changed).", text)
        self.assertNotIn("Actions: 0", text)

    def test_human_plan_renders_conflict_detail_before_next_action(self) -> None:
        text = render_human(
            {
                "operation": "update",
                "files": {"create": [], "replace": [], "remove": []},
                "conflicts": [
                    {
                        "code": "LOCAL_MODIFICATION",
                        "destination": "README.md",
                        "message": "restore the locked bytes, then rerun `plan`",
                    }
                ],
            },
            "plan",
        )
        conflict = "Conflict: LOCAL_MODIFICATION at README.md: restore the locked bytes, then rerun `plan`"
        self.assertIn(conflict, text)
        self.assertLess(text.index(conflict), text.index("Next: resolve every conflict"))
        self.assertIn("Do not apply this plan", text)

    def test_human_apply_conflict_does_not_suggest_validation(self) -> None:
        text = render_human(
            {
                "status": "conflict",
                "operation": "initial",
                "conflicts": ["README.md: destination exists with different bytes"],
            },
            "apply",
        )
        self.assertIn("Conflict: README.md: destination exists with different bytes", text)
        self.assertIn("Do not treat this apply as successful", text)
        self.assertNotIn("run validate before relying", text)

    def test_human_top_level_message_is_not_suppressed(self) -> None:
        text = render_human(
            {
                "status": "error",
                "code": "UPDATE_CONFIG_NOT_ALLOWED",
                "message": "Remove --config for update or use upgrade.",
            },
            "plan",
        )
        self.assertIn("Error: Remove --config for update or use upgrade.", text)
        self.assertIn("resolve the reported issue", text)
        self.assertNotIn("run apply with the same mode", text)

    def test_human_apply_reuses_structured_ownership_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_skill_config(config)
            result = self.run_composer(
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
                "--format",
                "human",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Composition apply", result.stdout)
            self.assertIn("Status: applied", result.stdout)
            self.assertIn("Ownership:", result.stdout)
            self.assertIn("Editable seeds:", result.stdout)
            self.assertIn("Next steps:", result.stdout)
            self.assertIn("Run `validate`", result.stdout)

    def test_human_validate_preserves_json_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_skill_config(config)
            applied = self.run_composer(
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)

            valid_json = self.run_composer("validate", "--target", str(target), "--format", "json")
            valid_human = self.run_composer("validate", "--target", str(target), "--format", "human")
            self.assertEqual(valid_json.returncode, valid_human.returncode)
            self.assertEqual(valid_human.returncode, 0, valid_human.stderr)
            self.assertEqual(json.loads(valid_json.stdout)["status"], "valid")
            self.assertIn("Composition validate", valid_human.stdout)
            self.assertIn("Status: valid", valid_human.stdout)

            (target / ".template-composition" / "lock.json").unlink()
            invalid_json = self.run_composer("validate", "--target", str(target), "--format", "json")
            invalid_human = self.run_composer("validate", "--target", str(target), "--format", "human")
            self.assertEqual(invalid_json.returncode, invalid_human.returncode)
            self.assertEqual(invalid_human.returncode, 2)
            self.assertEqual(json.loads(invalid_json.stdout)["status"], "invalid")
            self.assertIn("Status: invalid", invalid_human.stdout)
            self.assertIn("Error:", invalid_human.stdout)
            self.assertIn("run validate again", invalid_human.stdout)

    def test_invalid_public_format_fails_before_lifecycle_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "absent"
            result = self.run_composer(
                "inspect",
                "--target",
                str(target),
                "--format",
                "yaml",
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("argument --format: invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
