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
    classify_compatibility_paths,
    classify_paths,
    is_compatibility_sensitive_path,
    is_documentation_only_path,
    write_github_output,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"
CONSUMER_WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
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
            "components/artifact.webapp-core/component.json",
            "recipes/webapp.json",
            "tests/test_webapp_productization_acceptance.py",
            "examples/new-area/readme.txt",
            "component.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_documentation_only_path(path))

    def test_compatibility_sensitive_policy_is_conservative_and_future_proof(self) -> None:
        for path in (
            "scripts/compose.py",
            "scripts/new_future_helper.py",
            "tests/test_future_runtime.py",
            ".github/workflows/schema-validation.yml",
            ".github/workflows/future-runtime.yml",
            "requirements-runtime.lock",
            "release/composition-installer.json",
            "skills/composition/scripts/run.py",
            "skills/composition/SKILL.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_compatibility_sensitive_path(path))

        for path in (
            "README.md",
            "docs/index.md",
            "translations/ja/docs/index.md",
            "components/artifact.webapp-core/component.json",
            "recipes/webapp.json",
            "schemas/artifact.schema.json",
            "requirements-dev.lock",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_compatibility_sensitive_path(path))

    def test_unsafe_or_ambiguous_paths_fail_closed(self) -> None:
        for path in ("", "/docs/x.md", "../docs/x.md", "docs/../x.md", "docs\\x.md"):
            with self.subTest(path=path):
                self.assertFalse(is_documentation_only_path(path))
                self.assertTrue(is_compatibility_sensitive_path(path))
                required, reason = classify_paths([path])
                self.assertTrue(required)
                self.assertEqual(reason, "composition-sensitive-change")
                compatibility_required, compatibility_reason = classify_compatibility_paths(
                    [path]
                )
                self.assertTrue(compatibility_required)
                self.assertEqual(
                    compatibility_reason, "compatibility-sensitive-change"
                )

    def test_only_documentation_changes_can_skip_behavioral_and_compatibility_ci(self) -> None:
        paths = ["README.md", "docs/index.md", "translations/ja/docs/index.md"]
        required, reason = classify_paths(paths)
        self.assertFalse(required)
        self.assertEqual(reason, "documentation-only")

        compatibility_required, compatibility_reason = classify_compatibility_paths(paths)
        self.assertFalse(compatibility_required)
        self.assertEqual(compatibility_reason, "compatibility-insensitive-change")

    def test_behavioral_non_python_data_change_uses_fast_tier_only(self) -> None:
        paths = ["components/artifact.webapp-core/component.json", "recipes/webapp.json"]
        required, reason = classify_paths(paths)
        self.assertTrue(required)
        self.assertEqual(reason, "composition-sensitive-change")

        compatibility_required, compatibility_reason = classify_compatibility_paths(paths)
        self.assertFalse(compatibility_required)
        self.assertEqual(compatibility_reason, "compatibility-insensitive-change")

    def test_python_or_runtime_surface_requires_full_compatibility(self) -> None:
        for path in (
            "scripts/compose.py",
            "requirements-runtime.lock",
            "skills/composition/SKILL.md",
            ".github/workflows/composer-runtime.yml",
        ):
            with self.subTest(path=path):
                required, reason = classify_compatibility_paths([path])
                self.assertTrue(required)
                self.assertEqual(reason, "compatibility-sensitive-change")

    def test_mixed_unknown_and_empty_changes_fail_closed(self) -> None:
        required, reason = classify_paths(["docs/index.md", "scripts/compose.py"])
        self.assertTrue(required)
        self.assertEqual(reason, "composition-sensitive-change")

        compatibility_required, compatibility_reason = classify_compatibility_paths(
            ["docs/index.md", "scripts/compose.py"]
        )
        self.assertTrue(compatibility_required)
        self.assertEqual(compatibility_reason, "compatibility-sensitive-change")

        required, reason = classify_paths([])
        self.assertTrue(required)
        self.assertEqual(reason, "no-changes")
        compatibility_required, compatibility_reason = classify_compatibility_paths([])
        self.assertTrue(compatibility_required)
        self.assertEqual(compatibility_reason, "no-changes")

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
                compatibility_required=True,
                compatibility_reason="explicit-checkpoint",
                count=3,
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "required=false\n"
                "reason=documentation-only\n"
                "compatibility_required=true\n"
                "compatibility_reason=explicit-checkpoint\n"
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

    def test_consumer_workflow_uses_two_independent_fail_closed_classifications(self) -> None:
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
        self.assertIn(
            "compatibility_required: ${{ steps.classify.outputs.compatibility_required }}",
            classifier,
        )
        self.assertIn("--force-compatibility", classifier)
        self.assertIn("ci/full-compatibility", classifier)
        self.assertIn("refs/tags/composition-compatibility-", classifier)

        validate = workflow.split("\n  validate:\n", 1)[1]
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        self.assertIn("RUNTIME_REQUIRED: ${{ needs.classify_runtime.outputs.required }}", validate)
        self.assertIn(
            "COMPATIBILITY_REQUIRED: ${{ needs.classify_runtime.outputs.compatibility_required }}",
            validate,
        )
        self.assertIn('test "$CLASSIFIER_RESULT" = success', validate)
        self.assertIn('test "$CLEAN_RUNTIME_RESULT" = success', validate)
        self.assertIn('test "$CLEAN_RUNTIME_RESULT" = skipped', validate)
        self.assertIn('test "$COMPATIBILITY_CLEAN_RESULT" = success', validate)
        self.assertIn('test "$COMPATIBILITY_CLEAN_RESULT" = skipped', validate)
        self.assertIn(
            'echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"', validate
        )
        self.assertIn(
            'echo "invalid compatibility classification: $COMPATIBILITY_REQUIRED"',
            validate,
        )

    def test_consumer_trigger_keeps_authority_push_and_explicit_checkpoints(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        trigger = workflow.split("\njobs:\n", 1)[0]
        self.assertIn("push:", trigger)
        self.assertIn("- composition", trigger)
        self.assertIn("composition-compatibility-*", trigger)
        self.assertIn("labeled", trigger)
        self.assertIn("unlabeled", trigger)
        self.assertNotIn("paths-ignore:", trigger)
        self.assertNotIn("paths:", trigger)


if __name__ == "__main__":
    unittest.main()
