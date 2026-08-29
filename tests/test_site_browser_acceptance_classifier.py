from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.classify_site_browser_acceptance import (
    ClassificationError,
    SAFE_SKIP_EXACT_PATHS,
    classify_paths,
    is_safe_skip_path,
    normalize_path,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "classify_site_browser_acceptance.py"


class SiteBrowserAcceptanceClassifierTests(unittest.TestCase):
    def test_observability_only_changes_can_skip_browser_acceptance(self) -> None:
        required, reason, requiring = classify_paths(
            [
                ".github/workflows/ci-performance-report.yml",
                ".github/workflows/composition-unittest-timing-report.yml",
                "scripts/report_composition_unittest_timing.py",
                "tests/test_composition_unittest_timing_report.py",
                "tests/test_composition_unittest_timing_nonfinite.py",
            ]
        )

        self.assertFalse(required)
        self.assertEqual("all changed paths are CI-observability-only", reason)
        self.assertEqual((), requiring)

    def test_reader_runtime_build_and_unknown_changes_require_browser_acceptance(self) -> None:
        for path in (
            "docs/index.md",
            "stylesheets/extra.css",
            "javascripts/search-history.js",
            "service-worker.js",
            "scripts/check_pwa_freshness.py",
            "tests/test_mobile_layout.py",
            ".github/workflows/build-pages.yml",
            "scripts/classify_site_browser_acceptance.py",
            "README.md",
        ):
            with self.subTest(path=path):
                required, reason, requiring = classify_paths([path])
                self.assertTrue(required)
                self.assertEqual("non-observability path changed", reason)
                self.assertEqual((path,), requiring)

    def test_mixed_change_set_fails_closed_to_browser_required(self) -> None:
        required, reason, requiring = classify_paths(
            [
                "scripts/report_composition_unittest_timing.py",
                "docs/index.md",
                ".github/workflows/ci-performance-report.yml",
            ]
        )

        self.assertTrue(required)
        self.assertEqual("non-observability path changed", reason)
        self.assertEqual(("docs/index.md",), requiring)

    def test_safe_skip_surface_is_explicit_and_narrow(self) -> None:
        self.assertEqual(
            {
                ".github/workflows/ci-performance-report.yml",
                ".github/workflows/composition-unittest-timing-report.yml",
                "scripts/report_composition_unittest_timing.py",
            },
            set(SAFE_SKIP_EXACT_PATHS),
        )
        self.assertTrue(
            is_safe_skip_path("tests/test_composition_unittest_timing_schema_types.py")
        )
        self.assertFalse(is_safe_skip_path("tests/test_pwa_assets.py"))
        self.assertFalse(is_safe_skip_path("scripts/classify_site_browser_acceptance.py"))

    def test_paths_are_normalized_but_unsafe_forms_fail_closed(self) -> None:
        self.assertEqual(
            "tests/test_composition_unittest_timing_report.py",
            normalize_path(r"tests\test_composition_unittest_timing_report.py"),
        )
        for path in ("", "/absolute", "../escape", "docs//index.md", "./README.md"):
            with self.subTest(path=path):
                with self.assertRaises(ClassificationError):
                    normalize_path(path)

    def test_empty_change_set_fails_closed(self) -> None:
        with self.assertRaisesRegex(ClassificationError, "at least one changed path"):
            classify_paths([])

    def test_outputs_are_stable_and_machine_readable(self) -> None:
        output = io.StringIO()
        write_outputs(
            output,
            required=True,
            reason="non-observability path changed",
            changed_count=3,
            requiring_paths=("docs/index.md",),
        )

        self.assertEqual(
            [
                "required=true",
                "reason=non-observability path changed",
                "changed_count=3",
                "requiring_count=1",
                "requiring_paths=docs/index.md",
            ],
            output.getvalue().splitlines(),
        )

    def test_cli_rejects_empty_changed_path_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            changed = root / "changed.txt"
            output = root / "output.txt"
            changed.write_text("", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
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

            self.assertNotEqual(0, result.returncode)
            self.assertIn("classification failed", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
