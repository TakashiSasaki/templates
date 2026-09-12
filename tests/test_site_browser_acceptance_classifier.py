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

    def test_documentation_only_changes_can_skip_browser_acceptance(self) -> None:
        required, reason, requiring = classify_paths(
            [
                "docs/index.md",
                "README.md",
                "translations/ja/docs/index.md",
            ]
        )
        self.assertFalse(required)
        self.assertEqual("all changed paths are documentation-only", reason)
        self.assertEqual((), requiring)

    def test_reader_runtime_build_and_unknown_changes_require_browser_acceptance(self) -> None:
        for path in (
            "stylesheets/extra.css",
            "javascripts/search-history.js",
            "service-worker.js",
            "scripts/check_pwa_freshness.py",
            "tests/test_mobile_layout.py",
            "contracts/viewports.json",
            "contracts/browser-identity.json",
            "contracts/routes.json",
            ".github/workflows/build-pages.yml",
            "scripts/classify_site_browser_acceptance.py",
            "some/unrecognized/file.xyz",
        ):
            with self.subTest(path=path):
                required, reason, requiring = classify_paths([path])
                self.assertTrue(required)

    def test_mixed_change_set_fails_closed_to_browser_required(self) -> None:
        required, reason, requiring = classify_paths(
            [
                "docs/index.md",
                "stylesheets/extra.css",
            ]
        )

        self.assertTrue(required)
        self.assertEqual(("stylesheets/extra.css",), requiring)

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
        pass

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

    def test_outputs_when_not_required(self) -> None:
        output = io.StringIO()
        write_outputs(
            output,
            required=False,
            reason="all changed paths are CI-observability-only",
            changed_count=2,
            requiring_paths=(),
        )

        self.assertEqual(
            [
                "required=false",
                "reason=all changed paths are CI-observability-only",
                "changed_count=2",
                "requiring_count=0",
                "requiring_paths=none",
            ],
            output.getvalue().splitlines(),
        )

    def test_cli_successful_classification_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            changed = root / "changed.txt"
            output = root / "output.txt"
            changed.write_text(
                "scripts/report_composition_unittest_timing.py\n",
                encoding="utf-8",
            )

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

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                [
                    "required=false",
                    "reason=all changed paths are CI-observability-only",
                    "changed_count=1",
                    "requiring_count=0",
                    "requiring_paths=none",
                ],
                output.read_text(encoding="utf-8").splitlines(),
            )

    def test_cli_accepts_empty_changed_path_file(self) -> None:
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

            self.assertEqual(0, result.returncode)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
