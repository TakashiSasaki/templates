from __future__ import annotations

import unittest

from scripts.classify_site_ci import classify_paths


class AudienceCIClassificationTests(unittest.TestCase):
    def test_audience_runtime_surfaces_are_browser_sensitive(self) -> None:
        paths = (
            "assets/audience-runtime.json",
            "scripts/audience_context.py",
            "scripts/audience_presentation.py",
            "scripts/check_audience_artifact.py",
            "scripts/check_audience_runtime.py",
        )
        for path in paths:
            with self.subTest(path=path):
                decision = classify_paths([path])
                self.assertTrue(decision.core_required)
                self.assertTrue(decision.build_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.reference_consumer_required)
                self.assertFalse(decision.pwa_required)
                self.assertFalse(decision.cross_authority_required)
                self.assertFalse(decision.publication_required)
                self.assertFalse(decision.full_required)
                self.assertEqual("browser-sensitive", decision.risk_class)
                self.assertEqual("audience", decision.browser_priority)

    def test_combined_audience_delta_stays_out_of_full_qualification(self) -> None:
        paths = [
            "assets/audience-runtime.json",
            "scripts/audience_context.py",
            "scripts/audience_presentation.py",
            "scripts/check_audience_runtime.py",
        ]
        decision = classify_paths(paths)
        self.assertTrue(decision.build_required)
        self.assertTrue(decision.browser_required)
        self.assertFalse(decision.pwa_required)
        self.assertFalse(decision.cross_authority_required)
        self.assertFalse(decision.publication_required)
        self.assertFalse(decision.full_required)
        self.assertEqual("audience", decision.browser_priority)
        self.assertEqual(tuple(sorted(paths)), decision.requiring_paths)

    def test_audience_unit_tests_are_core_only(self) -> None:
        for path in (
            "tests/test_audience_context.py",
            "tests/test_audience_presentation.py",
            "tests/test_audience_artifact_integration.py",
            "tests/test_check_audience_runtime.py",
        ):
            with self.subTest(path=path):
                decision = classify_paths([path])
                self.assertTrue(decision.core_required)
                self.assertFalse(decision.build_required)
                self.assertFalse(decision.browser_required)
                self.assertFalse(decision.pwa_required)
                self.assertFalse(decision.full_required)
                self.assertFalse(decision.freshness_candidate_required)
                self.assertEqual("core-only", decision.risk_class)

    def test_unknown_script_remains_fail_closed(self) -> None:
        decision = classify_paths(["scripts/new_audience_like_but_unclassified.py"])
        self.assertTrue(decision.full_required)
        self.assertTrue(decision.pwa_required)
        self.assertTrue(decision.cross_authority_required)
        self.assertTrue(decision.publication_required)
        self.assertEqual("unknown", decision.risk_class)


if __name__ == "__main__":
    unittest.main()
