from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core  # noqa: E402
import composer_managed as managed  # noqa: E402


class ComposerSourceTransitionDiagnosticTests(unittest.TestCase):
    @staticmethod
    def git_result(returncode: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], returncode, stdout="", stderr="")

    def test_non_descendant_diagnostic_is_operation_neutral(self) -> None:
        old_revision = "1" * 40
        new_revision = "2" * 40
        with patch.object(
            core,
            "_run_git",
            side_effect=[self.git_result(0), self.git_result(1)],
        ):
            with self.assertRaises(managed.ManagedPlanError) as raised:
                managed._verify_source_transition(old_revision, new_revision)
        self.assertEqual(raised.exception.code, "SOURCE_REVISION_NOT_DESCENDANT")
        self.assertEqual(
            raised.exception.message,
            f"target composition source revision {new_revision} is not a descendant of old revision {old_revision}",
        )
        self.assertNotIn("update", raised.exception.message)

    def test_ancestry_probe_failure_diagnostic_is_operation_neutral(self) -> None:
        with patch.object(
            core,
            "_run_git",
            side_effect=[self.git_result(0), self.git_result(2)],
        ):
            with self.assertRaises(managed.ManagedPlanError) as raised:
                managed._verify_source_transition("1" * 40, "2" * 40)
        self.assertEqual(raised.exception.code, "GIT_FAILED")
        self.assertEqual(
            raised.exception.message,
            "cannot establish source revision ancestry for managed operation",
        )
        self.assertNotIn("update", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
