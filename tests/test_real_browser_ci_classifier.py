from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.classify_real_browser_ci import (
    ClassificationError,
    ZERO_SHA,
    changed_paths,
    classify_paths,
    is_documentation_only_path,
    write_github_output,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


class RealBrowserCIClassifierTests(unittest.TestCase):
    def test_documentation_only_allowlist_is_narrow(self) -> None:
        for path in (
            "README.md",
            "docs/consumer-guide.md",
            "docs/reference/composer.md",
            "translations/ja/docs/consumer-guide.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_documentation_only_path(path))

        for path in (
            "scripts/compose.py",
            "scripts/classify_real_browser_ci.py",
            ".github/workflows/schema-validation.yml",
            "components/artifact.webapp-core/component.json",
            "recipes/webapp.json",
            "tests/test_webapp_productization_acceptance.py",
            "examples/new-area/readme.txt",
            "component.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_documentation_only_path(path))

    def test_unsafe_or_ambiguous_paths_fail_closed(self) -> None:
        for path in ("", "/docs/x.md", "../docs/x.md", "docs/../x.md", "docs\\x.md"):
            with self.subTest(path=path):
                self.assertFalse(is_documentation_only_path(path))
                required, reason = classify_paths([path])
                self.assertTrue(required)
                self.assertEqual(reason, "browser-sensitive-change")

    def test_only_documentation_changes_can_skip_browser(self) -> None:
        required, reason = classify_paths(
            ["README.md", "docs/index.md", "translations/ja/docs/index.md"]
        )
        self.assertFalse(required)
        self.assertEqual(reason, "documentation-only")

    def test_mixed_unknown_and_empty_changes_fail_closed(self) -> None:
        required, reason = classify_paths(["docs/index.md", "scripts/compose.py"])
        self.assertTrue(required)
        self.assertEqual(reason, "browser-sensitive-change")

        required, reason = classify_paths([])
        self.assertTrue(required)
        self.assertEqual(reason, "no-changes")

    @patch("scripts.classify_real_browser_ci.subprocess.run")
    def test_git_diff_disables_rename_detection_and_parses_nul_paths(self, run) -> None:
        base = "1" * 40
        head = "2" * 40
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"docs/a.md\0scripts/compose.py\0",
            stderr=b"",
        )
        self.assertEqual(changed_paths(base, head), ["docs/a.md", "scripts/compose.py"])
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["git", "diff"])
        self.assertIn("--no-renames", command)
        self.assertIn("-z", command)
        self.assertEqual(command[-3:], [base, head, "--"])

    @patch("scripts.classify_real_browser_ci.subprocess.run")
    def test_git_diff_failure_is_explicit(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout=b"", stderr=b"missing revision"
        )
        with self.assertRaisesRegex(ClassificationError, "missing revision"):
            changed_paths("1" * 40, "2" * 40)

    def test_github_output_uses_only_stable_non_path_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            write_github_output(
                output,
                required=False,
                reason="documentation-only",
                count=3,
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "required=false\nreason=documentation-only\nchanged_count=3\n",
            )

    def test_zero_sha_is_the_explicit_unbounded_push_sentinel(self) -> None:
        self.assertEqual(ZERO_SHA, "0" * 40)

    def test_schema_workflow_conditions_browser_on_fail_closed_classifier(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  classify_browser:\n", workflow)
        self.assertIn("name: classify real-browser requirement", workflow)
        self.assertIn("id: classify", workflow)
        self.assertIn("scripts/classify_real_browser_ci.py", workflow)
        self.assertIn("required: ${{ steps.classify.outputs.required }}", workflow)
        self.assertIn("\n  real_browser:\n", workflow)
        self.assertIn("- classify_browser", workflow)
        self.assertIn(
            "if: needs.classify_browser.outputs.required == 'true'",
            workflow,
        )
        self.assertIn("CLASSIFIER_RESULT: ${{ needs.classify_browser.result }}", workflow)
        self.assertIn("BROWSER_REQUIRED: ${{ needs.classify_browser.outputs.required }}", workflow)
        self.assertIn("BROWSER_RESULT: ${{ needs.real_browser.result }}", workflow)
        self.assertIn('test "$CLASSIFIER_RESULT" = success', workflow)
        self.assertIn('test "$BROWSER_RESULT" = success', workflow)
        self.assertIn('test "$BROWSER_RESULT" = skipped', workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)


if __name__ == "__main__":
    unittest.main()
