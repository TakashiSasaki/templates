from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.classify_composition_ci import (
    ClassificationError,
    ZERO_SHA,
    changed_paths,
    classify_paths,
    is_documentation_only_path,
    write_github_output,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"
CONSUMER_WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
FULL_COMPATIBILITY_WORKFLOW = ROOT / ".github/workflows/composer-full-compatibility.yml"
CLASSIFIER = ROOT / "scripts/classify_composition_ci.py"
LEGACY_CLASSIFIER = ROOT / "scripts/classify_real_browser_ci.py"


class CompositionCIClassifierTests(unittest.TestCase):
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
            "AGENTS.md",
            ".agents/skills/pr-merge-gate/SKILL.md",
            "scripts/compose.py",
            "scripts/classify_composition_ci.py",
            ".github/workflows/schema-validation.yml",
            ".github/workflows/composer-runtime.yml",
            ".github/workflows/composer-full-compatibility.yml",
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
                self.assertEqual(reason, "composition-sensitive-change")

    def test_only_documentation_changes_can_skip_behavioral_ci(self) -> None:
        paths = ["README.md", "docs/index.md", "translations/ja/docs/index.md"]
        required, reason = classify_paths(paths)
        self.assertFalse(required)
        self.assertEqual(reason, "documentation-only")

    def test_every_non_documentation_change_requires_behavioral_ci(self) -> None:
        for paths in (
            ["components/artifact.webapp-core/component.json", "recipes/webapp.json"],
            ["scripts/compose.py"],
            ["requirements-runtime.lock"],
            ["skills/composition/SKILL.md"],
            [".github/workflows/composer-runtime.yml"],
        ):
            with self.subTest(paths=paths):
                required, reason = classify_paths(paths)
                self.assertTrue(required)
                self.assertEqual(reason, "composition-sensitive-change")

    def test_mixed_unknown_and_empty_changes_fail_closed(self) -> None:
        required, reason = classify_paths(["docs/index.md", "scripts/compose.py"])
        self.assertTrue(required)
        self.assertEqual(reason, "composition-sensitive-change")

        required, reason = classify_paths([])
        self.assertTrue(required)
        self.assertEqual(reason, "no-changes")

    @patch("scripts.classify_composition_ci.subprocess.run")
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

    @patch("scripts.classify_composition_ci.subprocess.run")
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
                "required=false\n"
                "reason=documentation-only\n"
                "changed_count=3\n",
            )

    def test_zero_sha_is_the_explicit_unbounded_push_sentinel(self) -> None:
        self.assertEqual(ZERO_SHA, "0" * 40)

    def test_generic_classifier_replaces_browser_named_implementation(self) -> None:
        self.assertTrue(CLASSIFIER.is_file())
        self.assertFalse(LEGACY_CLASSIFIER.exists())

    def test_schema_workflow_conditions_browser_on_fail_closed_classifier(self) -> None:
        workflow = SCHEMA_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  classify_browser:\n", workflow)
        self.assertIn("name: classify real-browser requirement", workflow)
        self.assertIn("id: classify", workflow)
        self.assertIn("scripts/classify_composition_ci.py", workflow)
        self.assertNotIn("scripts/classify_real_browser_ci.py", workflow)
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

    def test_consumer_workflow_uses_only_fail_closed_behavioral_classification(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        classifier = workflow.split("\n  classify_runtime:\n", 1)[1].split(
            "\n  clean-runtime:\n", 1
        )[0]
        self.assertIn("name: classify consumer-runtime requirement", classifier)
        self.assertNotIn("if: ${{ github.event_name == 'pull_request' }}", classifier)
        self.assertIn("scripts/classify_composition_ci.py", classifier)
        self.assertIn(
            "required: ${{ steps.classify.outputs.required }}", classifier
        )
        self.assertNotIn("compatibility_required", classifier)
        self.assertNotIn("force-compatibility", classifier)
        self.assertIn("Record runtime CI selection", classifier)
        self.assertIn("separate explicit qualification workflow", classifier)

        validate = workflow.split("\n  validate:\n", 1)[1]
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        self.assertIn("RUNTIME_REQUIRED: ${{ needs.classify_runtime.outputs.required }}", validate)
        self.assertNotIn("COMPATIBILITY_REQUIRED", validate)
        self.assertIn('test "$CLASSIFIER_RESULT" = success', validate)
        self.assertIn('test "$CLEAN_RUNTIME_RESULT" = success', validate)
        self.assertIn('test "$CLEAN_RUNTIME_RESULT" = skipped', validate)
        self.assertNotIn("COMPATIBILITY_CLEAN_RESULT", validate)
        self.assertIn(
            'echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"', validate
        )

    def test_consumer_trigger_is_only_authority_push_and_ordinary_pr(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        trigger = workflow.split("\njobs:\n", 1)[0]
        self.assertIn("push:", trigger)
        self.assertIn("- composition", trigger)
        self.assertIn("pull_request:", trigger)
        self.assertIn("opened", trigger)
        self.assertIn("synchronize", trigger)
        self.assertIn("reopened", trigger)
        self.assertNotIn("composition-compatibility-*", trigger)
        self.assertNotIn("labeled", trigger)
        self.assertNotIn("unlabeled", trigger)
        self.assertNotIn("paths-ignore:", trigger)
        self.assertNotIn("paths:", trigger)
        self.assertTrue(FULL_COMPATIBILITY_WORKFLOW.is_file())


if __name__ == "__main__":
    unittest.main()
