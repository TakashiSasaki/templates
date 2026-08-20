from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class ComposerPublicManagedInvalidInspectAcceptanceTests(unittest.TestCase):
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

    def write_config(self, path: Path) -> None:
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

    def test_inspect_classifies_managed_material_tamper_as_managed_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "composition.json"
            self.write_config(config_path)
            target = root / "consumer"

            result, payload = self.run_composer(
                "apply",
                "--config",
                str(config_path),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)

            managed_path = target / "docs" / "architecture.md"
            managed_path.write_bytes(managed_path.read_bytes() + b"managed tamper\n")
            tampered = managed_path.read_bytes()

            result, inspected = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 2, inspected)
            self.assertEqual(inspected["state"], "managed-invalid")
            self.assertTrue(
                any("managed material differs" in error for error in inspected["errors"]),
                inspected,
            )
            self.assertEqual(managed_path.read_bytes(), tampered)
            self.assertFalse((target / ".template-composition" / "transaction.json").exists())

            result, validated = self.run_composer("validate", "--target", str(target))
            self.assertEqual(result.returncode, 2, validated)
            self.assertEqual(validated["status"], "invalid")
            self.assertEqual(validated["errors"], inspected["errors"])
            self.assertEqual(managed_path.read_bytes(), tampered)


if __name__ == "__main__":
    unittest.main()
