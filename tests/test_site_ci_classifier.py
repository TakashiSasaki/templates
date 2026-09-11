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
        self.assertFalse(decision.freshness_candidate_required)
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
        self.assertFalse(decision.freshness_candidate_required)
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
        self.assertTrue(decision.reference_consumer_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertEqual("browser-sensitive", decision.risk_class)

    def test_visual_dependencies_require_browser_and_reference_consumer(self) -> None:
        decision = classify_paths(["requirements-visual.txt"])
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.reference_consumer_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("browser-sensitive", decision.risk_class)

    def test_playground_assets_and_scripts_require_browser(self) -> None:
        decision = classify_paths(
            [
                "assets/javascripts/composition-playground-explain.js",
                "scripts/check_composition_playground_browser.py",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.browser_required)
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
        self.assertTrue(decision.reference_consumer_required)
        self.assertEqual("pwa-sensitive", decision.risk_class)

    def test_actual_pwa_assets_require_pwa_and_browser(self) -> None:
        for pwa_path in ("assets/service-worker.js", "assets/javascripts/pwa.js"):
            with self.subTest(path=pwa_path):
                decision = classify_paths([pwa_path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.pwa_required)
                self.assertTrue(decision.reference_consumer_required)
                self.assertTrue(decision.freshness_candidate_required)
                self.assertFalse(decision.full_required)
                self.assertEqual("pwa-sensitive", decision.risk_class)

    def test_build_contracts_require_reference_consumer(self) -> None:
        decision = classify_paths(["scripts/site_website_contract.py"])
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.reference_consumer_required)
        self.assertFalse(decision.browser_required)
        self.assertFalse(decision.full_required)

    def test_publication_paths_require_publication_workflow(self) -> None:
        decision = classify_paths(
            [
                "scripts/prepare_repository_tree_publication.py",
                "site-manifest.json",
                "PUBLICATION_FRESHNESS.md",
            ]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.publication_required)
        self.assertFalse(decision.full_required)

    def test_translation_manifest_requires_build_and_publication(self) -> None:
        decision = classify_paths(["translations/manifest.json"])
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.publication_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("publication-sensitive", decision.risk_class)

    def test_publication_freshness_contract_requires_candidate_build(self) -> None:
        decision = classify_paths(["PUBLICATION_FRESHNESS.md"])
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.publication_required)
        self.assertEqual("publication-sensitive", decision.risk_class)

    def test_unlisted_runtime_build_inputs_require_freshness_candidate_build(self) -> None:
        decision = classify_paths(
            ["scripts/generate_repository_file_previews_composition.py"]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertFalse(decision.browser_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.publication_required)
        self.assertFalse(decision.full_required)
        self.assertTrue(decision.freshness_candidate_required)
        self.assertEqual("runtime-sensitive", decision.risk_class)

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

    def test_cross_authority_playground_scripts_require_cross_authority(self) -> None:
        scripts = (
            "scripts/check_composition_playground_cross_authority.py",
            "scripts/check_composition_playground_webmcp_browser.py",
            "scripts/check_composition_playground_latest_five_browser.py",
            "scripts/check_composition_playground_final_browser.py",
            "scripts/check_composition_playground_final_grid_browser.py",
        )
        for ca_script in scripts:
            with self.subTest(script=ca_script):
                decision = classify_paths([ca_script])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.cross_authority_required)
                self.assertTrue(decision.publication_required)
                self.assertTrue(decision.reference_consumer_required)
                self.assertTrue(decision.freshness_candidate_required)
                self.assertFalse(decision.full_required)
                self.assertEqual("cross-authority-sensitive", decision.risk_class)

        decision = classify_paths(
            ["tests/test_composition_playground_cross_authority_workflow.py"]
        )
        self.assertTrue(decision.core_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertFalse(decision.browser_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("cross-authority-sensitive", decision.risk_class)

    def test_ci_workflow_and_classifier_changes_fail_closed_to_full(self) -> None:
        for path in (
            ".github/workflows/build-pages.yml",
            ".github/workflows/reference-consumer.yml",
            ".github/workflows/site-composition-playground-cross-authority.yml",
            ".github/workflows/site-full-qualification.yml",
            "scripts/classify_site_ci.py",
            "scripts/classify_site_browser_acceptance.py",
            "scripts/verify_site_full_qualification.py",
            "scripts/run_core_tests.py",
            "tests/test_site_ci_classifier.py",
            "tests/test_run_core_tests.py",
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
            self.assertIn("coexistence_required=false\n", content)
            self.assertIn("freshness_candidate_required=false\n", content)
            self.assertIn("risk_class=documentation-only\n", content)

    def test_coexistence_required_for_full_and_python_paths(self) -> None:
        # Full qualification paths must evaluate coexistence_required=True
        for path in (
            ".github/workflows/reference-consumer.yml",
            "some/unknown/file.xyz",
        ):
            with self.subTest(path=path):
                decision = classify_paths([path])
                self.assertTrue(decision.full_required)
                self.assertTrue(decision.coexistence_required)

        # Python and provider lock paths must evaluate coexistence_required=True
        for path in (
            "scripts/resolve_publication_sources.py",
            "publication-sources.json",
            ".github/workflows/provider-coexistence.yml",
        ):
            with self.subTest(path=path):
                decision = classify_paths([path])
                self.assertTrue(decision.coexistence_required)

        # Docs-only paths must evaluate coexistence_required=False
        decision = classify_paths(["docs/index.md"])
        self.assertFalse(decision.coexistence_required)

    def test_browser_contracts_require_browser_and_reference_consumer(self) -> None:
        browser_contracts = (
            "contracts/viewports.json",
            "contracts/browser-identity.json",
            "contracts/routes.json",
            "contracts/site-structure.json",
            "contracts/document-metadata.json",
            "contracts/site-discovery.json",
            "contracts/manifest.json",
        )
        for contract_path in browser_contracts:
            with self.subTest(contract=contract_path):
                decision = classify_paths([contract_path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.reference_consumer_required)
                self.assertFalse(decision.pwa_required)
                self.assertFalse(decision.cross_authority_required)
                self.assertFalse(decision.full_required)
                self.assertTrue(decision.freshness_candidate_required)
                self.assertEqual("browser-sensitive", decision.risk_class)

    def test_consumer_evidence_contracts_require_reference_consumer(self) -> None:
        for contract_path in (
            "contracts/implementation-evidence.json",
            "contracts/lifecycle-checkpoints.json",
        ):
            with self.subTest(contract=contract_path):
                decision = classify_paths([contract_path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertFalse(decision.browser_required)
                self.assertTrue(decision.reference_consumer_required)
                self.assertFalse(decision.pwa_required)
                self.assertFalse(decision.cross_authority_required)
                self.assertFalse(decision.full_required)
                self.assertTrue(decision.freshness_candidate_required)
                self.assertEqual("runtime-sensitive", decision.risk_class)

    def test_known_build_only_scripts_require_build_but_skip_browser(self) -> None:
        for script_path in (
            "scripts/generate_repository_browser.py",
            "scripts/generate_index_navigation.py",
            "scripts/finalize_site_metadata.py",
            "scripts/site_build_profile.py",
        ):
            with self.subTest(script=script_path):
                decision = classify_paths([script_path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertFalse(decision.browser_required)
                self.assertFalse(decision.pwa_required)
                self.assertFalse(decision.publication_required)
                self.assertFalse(decision.cross_authority_required)
                self.assertFalse(decision.full_required)
                self.assertTrue(decision.freshness_candidate_required)
                self.assertEqual("runtime-sensitive", decision.risk_class)

    def test_pwa_icon_assets_require_pwa_and_browser(self) -> None:
        for icon_path in (
            "assets/icon-180.png",
            "assets/icon-192.png",
            "assets/icon-512.png",
            "assets/icon.svg",
            "assets/app.webmanifest",
        ):
            with self.subTest(icon=icon_path):
                decision = classify_paths([icon_path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.pwa_required)
                self.assertFalse(decision.full_required)
                self.assertEqual("pwa-sensitive", decision.risk_class)

    def test_unknown_new_script_fails_closed_to_full(self) -> None:
        decision = classify_paths(["scripts/new_generator.py"])
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.pwa_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertTrue(decision.coexistence_required)
        self.assertEqual("unknown", decision.risk_class)
        self.assertIn("unknown changed paths: scripts/new_generator.py", decision.reason)

    def test_unknown_new_contract_fails_closed_to_full(self) -> None:
        decision = classify_paths(["contracts/new-runtime.json"])
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.pwa_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertTrue(decision.coexistence_required)
        self.assertEqual("unknown", decision.risk_class)
        self.assertIn("unknown changed paths: contracts/new-runtime.json", decision.reason)

    def test_unknown_top_level_file_fails_closed_to_full(self) -> None:
        decision = classify_paths(["new-top-level-file.xyz"])
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertTrue(decision.pwa_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertTrue(decision.coexistence_required)
        self.assertEqual("unknown", decision.risk_class)
        self.assertIn("unknown changed paths: new-top-level-file.xyz", decision.reason)


if __name__ == "__main__":
    unittest.main()

