from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "composition" / "scripts" / "run.py"


class CompositionSkillCliTests(unittest.TestCase):
    def test_help_is_available_without_network_or_repository_access(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(RUNNER), "--help"],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--repository", result.stdout)
        self.assertIn("--revision", result.stdout)
        self.assertIn("inspect", result.stdout)
        self.assertIn("validate", result.stdout)

    def test_forwarded_target_is_rejected_before_runtime_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER),
                    "--repository",
                    str(repository),
                    "inspect",
                    "--target",
                    str(repository),
                ],
                check=False,
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("do not pass Composer --target", result.stderr)

    def test_mutable_revision_name_is_rejected_before_network_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER),
                    "--repository",
                    str(repository),
                    "--revision",
                    "composition",
                    "inspect",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("full lowercase 40-character commit SHA", result.stderr)


if __name__ == "__main__":
    unittest.main()
