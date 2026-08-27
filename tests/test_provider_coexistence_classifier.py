from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.classify_provider_coexistence import (
    ClassificationError,
    classify_paths,
    normalize_path,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "classify_provider_coexistence.py"


class ProviderCoexistenceClassifierTests(unittest.TestCase):
    def test_reader_facing_site_changes_can_skip_heavy_provider_setup(self) -> None:
        required, matched = classify_paths(
            [
                "docs/getting-started.md",
                "translations/ja/docs/getting-started.md",
                "stylesheets/extra.css",
                "javascripts/search-history.js",
            ]
        )

        self.assertFalse(required)
        self.assertEqual(matched, ())

    def test_provider_lock_and_workflow_changes_require_validation(self) -> None:
        for path in (
            "publication-sources.json",
            ".github/workflows/provider-coexistence.yml",
        ):
            with self.subTest(path=path):
                required, matched = classify_paths([path])
                self.assertTrue(required)
                self.assertEqual(matched, (path,))

    def test_any_python_change_fails_closed_to_provider_validation(self) -> None:
        for path in (
            "scripts/resolve_publication_sources.py",
            "scripts/validate_provider_coexistence.py",
            "scripts/future_integration_helper.py",
            "tests/test_provider_coexistence_integration.py",
            "tools/future_helper.py",
        ):
            with self.subTest(path=path):
                required, matched = classify_paths([path])
                self.assertTrue(required)
                self.assertEqual(matched, (path,))

    def test_mixed_scope_runs_when_any_path_is_relevant(self) -> None:
        required, matched = classify_paths(
            [
                "docs/reader.md",
                "scripts/validate_provider_coexistence.py",
                "stylesheets/extra.css",
            ]
        )

        self.assertTrue(required)
        self.assertEqual(matched, ("scripts/validate_provider_coexistence.py",))

    def test_classifier_deduplicates_and_sorts_multiple_matching_paths(self) -> None:
        required, matched = classify_paths(
            [
                "scripts/validate_provider_coexistence.py",
                "publication-sources.json",
                "scripts/validate_provider_coexistence.py",
            ]
        )

        self.assertTrue(required)
        self.assertEqual(
            matched,
            (
                "publication-sources.json",
                "scripts/validate_provider_coexistence.py",
            ),
        )

    def test_windows_separators_are_normalized_before_classification(self) -> None:
        self.assertEqual(
            normalize_path(r"scripts\validate_provider_coexistence.py"),
            "scripts/validate_provider_coexistence.py",
        )

    def test_empty_or_non_repository_relative_input_fails_closed(self) -> None:
        for value in ("", "/absolute/path.py", "../outside.py", "docs//reader.md"):
            with self.subTest(value=value):
                with self.assertRaises(ClassificationError):
                    classify_paths([value])
        with self.assertRaises(ClassificationError):
            classify_paths([])

    def test_outputs_are_explicit_for_required_and_skipped_scopes(self) -> None:
        required_output = io.StringIO()
        write_outputs(
            required_output,
            required=True,
            matched=("publication-sources.json",),
        )
        self.assertEqual(
            required_output.getvalue(),
            "required=true\nmatched_count=1\nmatched_paths=publication-sources.json\n",
        )

        skipped_output = io.StringIO()
        write_outputs(skipped_output, required=False, matched=())
        self.assertEqual(
            skipped_output.getvalue(),
            "required=false\nmatched_count=0\nmatched_paths=none\n",
        )

    def test_cli_reads_changed_paths_and_writes_github_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            changed = root / "changed.txt"
            output = root / "github-output.txt"
            changed.write_text(
                "docs/reader.md\nscripts/resolve_publication_sources.py\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLASSIFIER),
                    "--changed-paths",
                    str(changed),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "required=true\n"
                "matched_count=1\n"
                "matched_paths=scripts/resolve_publication_sources.py\n",
            )

    def test_cli_fails_closed_on_invalid_changed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            changed = root / "changed.txt"
            output = root / "github-output.txt"
            changed.write_text("/absolute/path.py\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLASSIFIER),
                    "--changed-paths",
                    str(changed),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "provider coexistence classification failed:",
                result.stderr,
            )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
