from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_source


class GitSourceContextTests(unittest.TestCase):
    def test_revision_requires_clean_full_sha(self) -> None:
        context = composer_source.GitSourceContext(ROOT)
        revision = "1" * 40
        outputs = iter(
            (
                subprocess.CompletedProcess([], 0, stdout=revision + "\n", stderr=""),
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            )
        )
        with mock.patch("composer_source.subprocess.run", side_effect=lambda *_a, **_k: next(outputs)):
            self.assertEqual(context.revision(), revision)

    def test_revision_rejects_dirty_checkout(self) -> None:
        context = composer_source.GitSourceContext(ROOT)
        outputs = iter(
            (
                subprocess.CompletedProcess([], 0, stdout="1" * 40 + "\n", stderr=""),
                subprocess.CompletedProcess([], 0, stdout=" M catalog/catalog.json\n", stderr=""),
            )
        )
        with mock.patch("composer_source.subprocess.run", side_effect=lambda *_a, **_k: next(outputs)):
            with self.assertRaisesRegex(
                composer_source.SourceContextError,
                "tracked modifications",
            ) as caught:
                context.revision()
        self.assertEqual(caught.exception.code, "DIRTY_SOURCE")

    def test_assert_authority_rejects_untracked_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "authority.json"
            path.write_text("{}\n", encoding="utf-8")
            context = composer_source.GitSourceContext(root)
            result = subprocess.CompletedProcess([], 1, stdout="", stderr="not tracked")
            with mock.patch.object(
                composer_source.GitSourceContext,
                "run_git",
                autospec=True,
                return_value=result,
            ):
                with self.assertRaisesRegex(
                    composer_source.SourceContextError,
                    "not tracked",
                ) as caught:
                    context.assert_authority(path)
            self.assertEqual(caught.exception.code, "UNTRACKED_SOURCE_AUTHORITY")

    def test_verify_descendant_accepts_ancestor(self) -> None:
        context = composer_source.GitSourceContext(ROOT)
        success = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(
            composer_source.GitSourceContext,
            "run_git",
            autospec=True,
            return_value=success,
        ) as run_git:
            context.verify_descendant("1" * 40, "2" * 40)
        self.assertEqual(run_git.call_count, 2)

    def test_verify_descendant_rejects_divergence(self) -> None:
        context = composer_source.GitSourceContext(ROOT)
        results = iter(
            (
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess([], 1, stdout="", stderr=""),
            )
        )
        with mock.patch.object(
            composer_source.GitSourceContext,
            "run_git",
            autospec=True,
            side_effect=lambda *_a, **_k: next(results),
        ):
            with self.assertRaisesRegex(
                composer_source.SourceContextError,
                "not a descendant",
            ) as caught:
                context.verify_descendant("1" * 40, "2" * 40)
        self.assertEqual(caught.exception.code, "SOURCE_REVISION_NOT_DESCENDANT")

    def test_git_execution_failure_has_stable_diagnostic(self) -> None:
        context = composer_source.GitSourceContext(ROOT)
        with mock.patch(
            "composer_source.subprocess.run",
            side_effect=OSError("missing git"),
        ):
            with self.assertRaisesRegex(
                composer_source.SourceContextError,
                "cannot execute git",
            ) as caught:
                context.run_git("rev-parse", "HEAD")
        self.assertEqual(caught.exception.code, "GIT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
