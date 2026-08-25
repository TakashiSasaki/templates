from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


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

    def test_human_validate_preserves_status_and_exit_code(self) -> None:
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

            valid = self.run_composer(
                "validate",
                "--target",
                str(target),
                "--format",
                "human",
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("Composition validate", valid.stdout)
            self.assertIn("Status: valid", valid.stdout)
            self.assertIn("Next:", valid.stdout)

            (target / ".template-composition" / "lock.json").unlink()
            invalid = self.run_composer(
                "validate",
                "--target",
                str(target),
                "--format",
                "human",
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("Status: invalid", invalid.stdout)
            self.assertIn("Error:", invalid.stdout)
            self.assertIn("run validate again", invalid.stdout)

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
