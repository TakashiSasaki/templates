from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core  # noqa: E402
import composer_managed as managed  # noqa: E402
import composer_source  # noqa: E402


class ComposerSourceTransitionDiagnosticTests(unittest.TestCase):
    def test_non_descendant_diagnostic_is_operation_neutral(self) -> None:
        old_revision = "1" * 40
        new_revision = "2" * 40
        context = Mock()
        context.verify_descendant.side_effect = composer_source.SourceContextError(
            "SOURCE_REVISION_NOT_DESCENDANT",
            f"target composition source revision {new_revision} is not a descendant of old revision {old_revision}",
        )
        with patch.object(core, "source_context", return_value=context):
            with self.assertRaises(managed.ManagedPlanError) as raised:
                managed._verify_source_transition(old_revision, new_revision)
        self.assertEqual(raised.exception.code, "SOURCE_REVISION_NOT_DESCENDANT")
        self.assertEqual(
            raised.exception.message,
            f"target composition source revision {new_revision} is not a descendant of old revision {old_revision}",
        )
        self.assertNotIn("update", raised.exception.message)

    def test_ancestry_probe_failure_diagnostic_is_operation_neutral(self) -> None:
        context = Mock()
        context.verify_descendant.side_effect = composer_source.SourceContextError(
            "GIT_FAILED",
            "cannot establish source revision ancestry for managed operation",
        )
        with patch.object(core, "source_context", return_value=context):
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
