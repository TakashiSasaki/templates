from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class HumanValidationSummaryContractTests(unittest.TestCase):
    def test_human_output_summarizes_passed_validator_without_replaying_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipe": "webapp",
                        "components": {"include": [], "exclude": []},
                        "parameters": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            applied = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--config",
                    str(config),
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

            runner = target / ".template-composition" / "validate.py"
            human = subprocess.run(
                [sys.executable, str(runner), str(target)],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(human.returncode, 0, human.stdout + human.stderr)
            self.assertIn("PASSED: implementation-evidence", human.stdout)
            self.assertIn("Composition validation: VALID", human.stdout)
            self.assertNotIn("Implementation evidence validation: OK", human.stdout)


if __name__ == "__main__":
    unittest.main()
