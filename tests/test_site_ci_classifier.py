from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.classify_site_ci import (
    classify_paths,
)

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "classify_site_ci.py"


class SiteCIClassifierTests(unittest.TestCase):
    def test_observability_only_changes_skip_all_heavy_stages(self) -> None:
        decision = classify_paths(
            [
                ".github/workflows/ci-performance-report.yml",
                ".github/workflows/composition-unittest-timing-report.yml",
                "scripts/report_composition_unittest_timing.py",
                "tests/test_composition_unittest_timing_report.py",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertFalse(decision.build_required)
        self.assertFalse(decision.browser_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("observability-only", decision.risk_class)

    def test_docs_only_changes_skip_build_and_browser(self) -> None:
        decision = classify_paths(
            [
                "docs/index.md",
                "docs/getting-started.md",
                "translations/ja/docs/index.md",
                "README.md",
                "MAINTENANCE.md",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertFalse(decision.build_required)
        self.assertFalse(decision.browser_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("documentation-only", decision.risk_class)

    def test_browser_and_css_changes_require_browser_and_build(self) -> None:
        decision = classify_paths(
            [
                "stylesheets/extra.css",
                "javascripts/search-history.js",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertEqual("browser-sensitive", decision.risk_class)

    def test_pwa_changes_require_pwa_and_browser(self) -> None:
        decision = classify_paths(
            [
                "service-worker.js",
                "scripts/check_pwa_freshness.py",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.pwa_required)
        self.assertEqual("pwa-sensitive", decision.risk_class)

    def test_cross_authority_changes_require_cross_authority(self) -> None:
        decision = classify_paths(
            [
                "publication-sources.json",
                "scripts/resolve_publication_sources.py",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertEqual("cross-authority-sensitive", decision.risk_class)

    def test_ci_workflow_and_classifier_changes_fail_closed_to_full(self) -> None:
        for path in (
            ".github/workflows/build-pages.yml",
            ".github/workflows/reference-consumer.yml",
            ".github/workflows/site-composition-playground-cross-authority.yml",
            "scripts/classify_site_ci.py",
            "scripts/classify_site_browser_acceptance.py",
        ):
            with self.subTest(path=path):
                decision = classify_paths([path])
                self.assertTrue(decision.full_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertEqual("ci-authority-sensitive", decision.risk_class)

    def test_ci_control_changes_cannot_self_exempt_even_with_docs(self) -> None:
        decision = classify_paths(
            [
                "docs/index.md",
                "README.md",
                ".github/workflows/build-pages.yml",
            ]
        )
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertEqual("ci-authority-sensitive", decision.risk_class)

    def test_mixed_docs_and_browser_takes_strictest_scope(self) -> None:
        decision = classify_paths(
            [
                "docs/index.md",
                "stylesheets/extra.css",
            ]
        )
        self.assertFalse(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertEqual("browser-sensitive", decision.risk_class)

    def test_unknown_paths_fail_closed_to_full(self) -> None:
        decision = classify_paths(["some/random/unrecognized_file.xyz"])
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertEqual("unknown", decision.risk_class)

    def test_force_full_override(self) -> None:
        decision = classify_paths(["docs/index.md"], force_full=True)
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.pwa_required)
        self.assertEqual("explicit full qualification requested", decision.reason)

    def test_cli_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            changed = root / "changed.txt"
            output = root / "output.txt"
            changed.write_text("docs/index.md\n", encoding="utf-8")

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
            content = output.read_text(encoding="utf-8")
            self.assertIn("core_required=true\n", content)
            self.assertIn("build_required=false\n", content)
            self.assertIn("browser_required=false\n", content)
            self.assertIn("full_required=false\n", content)
            self.assertIn("risk_class=documentation-only\n", content)


if __name__ == "__main__":
    unittest.main()
