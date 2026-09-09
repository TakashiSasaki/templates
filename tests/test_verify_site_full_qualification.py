from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.verify_site_full_qualification import REQUIRED_SUITES, verify_qualification


class VerifySiteFullQualificationTests(unittest.TestCase):
    def test_required_suites_count(self) -> None:
        self.assertEqual(19, len(REQUIRED_SUITES))
        keys = [k for k, _, _ in REQUIRED_SUITES]
        self.assertEqual(len(keys), len(set(keys)), "Suite keys must be unique")

    @patch("scripts.verify_site_full_qualification.fetch_check_runs")
    def test_all_green_check_runs_returns_zero(self, mock_fetch) -> None:
        mock_runs = []
        for key, description, predicate in REQUIRED_SUITES:
            sample_name = {
                "build": "build",
                "check": "check",
                "construction_gate": "Site Construction CI / validate",
                "provider_coexistence": "Validate exact provider coexistence",
                "provider_coexistence_gate": "Provider coexistence gate",
                "ref_consumer_composition": "composition",
                "ref_consumer_build": "build / build",
                "ref_consumer_browser": "browser",
                "pub_freshness_resolve": "resolve",
                "pub_freshness_build": "Build with current Composition HEAD / build",
                "pub_freshness_report": "report",
                "pub_materialization": "materialization",
                "pub_contract": "contract",
                "cross_auth_build": "Build exact cross-authority candidate / build",
                "cross_auth_consumer": "Real producer to Chromium consumer",
                "playground_consumer": "projection consumer",
                "playground_explain": "projection explanations and browser acceptance",
                "validate_website": "validate-website",
                "policy": "policy",
            }[key]
            mock_runs.append({
                "id": hash(key),
                "name": sample_name,
                "status": "completed",
                "conclusion": "success",
            })

        mock_fetch.return_value = mock_runs
        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=1,
            poll_interval_seconds=0,
        )
        self.assertEqual(0, result)

    @patch("scripts.verify_site_full_qualification.fetch_check_runs")
    def test_failed_check_run_returns_one(self, mock_fetch) -> None:
        mock_runs = [
            {"id": 1, "name": "build", "status": "completed", "conclusion": "failure", "html_url": "http://fail"},
        ]
        mock_fetch.return_value = mock_runs
        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=1,
            poll_interval_seconds=0,
        )
        self.assertEqual(1, result)

    @patch("scripts.verify_site_full_qualification.fetch_check_runs")
    def test_reusable_workflow_prefixed_construction_gate_not_matched(self, mock_fetch) -> None:
        # Reusable workflow caller prefix should NOT be matched by construction_gate
        mock_runs = [
            {
                "id": 100,
                "name": "Build exact cross-authority candidate / Site Construction CI / validate",
                "status": "completed",
                "conclusion": "skipped",
            },
        ]
        mock_fetch.return_value = mock_runs
        for key, description, predicate in REQUIRED_SUITES:
            if key == "construction_gate":
                self.assertFalse(predicate("Build exact cross-authority candidate / Site Construction CI / validate"))
                self.assertTrue(predicate("Site Construction CI / validate"))
                self.assertTrue(predicate("Site CI / validate"))

    @patch("scripts.verify_site_full_qualification.fetch_check_runs")
    def test_incomplete_check_runs_timeout_returns_one(self, mock_fetch) -> None:
        mock_runs = [
            {"id": 1, "name": "build", "status": "in_progress", "conclusion": None},
        ]
        mock_fetch.return_value = mock_runs
        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=0,
            poll_interval_seconds=0,
        )
        self.assertEqual(1, result)


if __name__ == "__main__":
    unittest.main()
