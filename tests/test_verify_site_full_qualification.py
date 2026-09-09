from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from scripts.verify_site_full_qualification import (
    EXTERNAL_WORKFLOW_PATHS,
    REQUIRED_SUITES,
    evaluate_suites,
    verify_qualification,
)


def build_mock_hierarchy(
    *,
    status_overrides: dict[str, str] | None = None,
    conclusion_overrides: dict[str, str | None] | None = None,
    missing_suites: set[str] | None = None,
    missing_workflow_paths: set[str] | None = None,
    extra_jobs_by_path: dict[str, list[dict]] | None = None,
):
    """Builds realistic workflow_runs and run_jobs structures matching GitHub Actions API."""
    status_overrides = status_overrides or {}
    conclusion_overrides = conclusion_overrides or {}
    missing_suites = missing_suites or set()
    missing_workflow_paths = missing_workflow_paths or set()
    extra_jobs_by_path = extra_jobs_by_path or {}

    runs = []
    jobs_by_run_id = {}

    # Assign distinct integer run IDs to workflow paths
    path_to_run_id = {}
    for i, path in enumerate(EXTERNAL_WORKFLOW_PATHS, start=1000):
        if path in missing_workflow_paths:
            continue
        path_to_run_id[path] = i
        runs.append({
            "id": i,
            "name": path.split("/")[-1].replace(".yml", ""),
            "path": path,
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request",
            "html_url": f"https://github.com/TakashiSasaki/templates/actions/runs/{i}",
        })
        jobs_by_run_id[i] = []

    # Populate jobs for each suite
    for suite in REQUIRED_SUITES:
        if suite.key in missing_suites:
            continue
        run_id = path_to_run_id.get(suite.workflow_path)
        if run_id is None:
            continue
        status = status_overrides.get(suite.key, "completed")
        conclusion = conclusion_overrides.get(suite.key, "success" if status == "completed" else None)
        jobs_by_run_id[run_id].append({
            "id": hash(suite.key) & 0x7FFFFFFF,
            "name": suite.job_name,
            "status": status,
            "conclusion": conclusion,
            "html_url": f"https://github.com/TakashiSasaki/templates/actions/runs/{run_id}/jobs/{hash(suite.key) & 0x7FFFFFFF}",
        })

    # Add extra jobs to specific workflow paths (for collision testing)
    for path, extra_jobs in extra_jobs_by_path.items():
        run_id = path_to_run_id.get(path)
        if run_id is not None:
            jobs_by_run_id[run_id].extend(extra_jobs)

    # Sync workflow run status with its jobs (realistic GitHub Actions semantics)
    for run in runs:
        run_id = run["id"]
        run_jobs = jobs_by_run_id.get(run_id, [])
        if any(j.get("status") != "completed" for j in run_jobs):
            run["status"] = "in_progress"
            run["conclusion"] = None
        else:
            run["status"] = "completed"
            if any(j.get("conclusion") == "failure" for j in run_jobs):
                run["conclusion"] = "failure"
            elif all(j.get("conclusion") == "success" for j in run_jobs):
                run["conclusion"] = "success"

    return runs, jobs_by_run_id


class VerifySiteFullQualificationTests(unittest.TestCase):
    def test_required_suites_count(self) -> None:
        self.assertEqual(19, len(REQUIRED_SUITES))
        keys = [s.key for s in REQUIRED_SUITES]
        self.assertEqual(len(keys), len(set(keys)), "Suite keys must be unique")

    def test_no_aggregate_self_dependency(self) -> None:
        self.assertNotIn(
            ".github/workflows/site-full-qualification.yml",
            EXTERNAL_WORKFLOW_PATHS,
            "Site full qualification must not depend on itself",
        )
        for suite in REQUIRED_SUITES:
            self.assertNotEqual(
                ".github/workflows/site-full-qualification.yml",
                suite.workflow_path,
                "No required suite can belong to site-full-qualification.yml",
            )

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_all_green_exact_head_l3_checks_returns_zero(self, mock_runs, mock_jobs) -> None:
        runs, jobs_by_id = build_mock_hierarchy()
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=1,
            poll_interval_seconds=0,
        )
        self.assertEqual(0, result)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_direct_construction_gate_success_nested_reusable_construction_gate_skipped(
        self, mock_runs, mock_jobs
    ) -> None:
        # Cross-authority workflow calls build-pages.yml as reusable workflow, producing
        # a skipped nested job "Build exact cross-authority candidate / Site Construction CI / validate"
        extra = {
            ".github/workflows/site-composition-playground-cross-authority.yml": [
                {
                    "id": 99999,
                    "name": "Build exact cross-authority candidate / Site Construction CI / validate",
                    "status": "completed",
                    "conclusion": "skipped",
                    "html_url": "http://skipped-nested",
                }
            ]
        }
        runs, jobs_by_id = build_mock_hierarchy(extra_jobs_by_path=extra)
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=1,
            poll_interval_seconds=0,
        )
        # Must succeed because construction_gate is queried from build-pages.yml, NOT cross-authority
        self.assertEqual(0, result)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_same_job_name_in_two_workflows_selects_correct_identity(
        self, mock_runs, mock_jobs
    ) -> None:
        # Both build-pages.yml and another workflow contain a job named "build",
        # but the second one has conclusion="failure"
        extra = {
            ".github/workflows/reference-consumer.yml": [
                {
                    "id": 88888,
                    "name": "build",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "http://unrelated-fail",
                }
            ]
        }
        runs, jobs_by_id = build_mock_hierarchy(extra_jobs_by_path=extra)
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=1,
            poll_interval_seconds=0,
        )
        # Must succeed because "build" suite is bound to build-pages.yml, not reference-consumer.yml
        self.assertEqual(0, result)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_required_check_missing_returns_one(self, mock_runs, mock_jobs) -> None:
        # A required workflow path is entirely missing
        missing_wf = {".github/workflows/validate-website.yml"}
        runs, jobs_by_id = build_mock_hierarchy(missing_workflow_paths=missing_wf)
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=0,
            poll_interval_seconds=0,
        )
        self.assertEqual(1, result)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_required_check_failure_returns_one(self, mock_runs, mock_jobs) -> None:
        runs, jobs_by_id = build_mock_hierarchy(
            status_overrides={"build": "completed"},
            conclusion_overrides={"build": "failure"},
        )
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            result = verify_qualification(
                repo="TakashiSasaki/templates",
                head_sha="0123456789abcdef",
                token="dummy",
                timeout_seconds=1,
                poll_interval_seconds=0,
            )
        self.assertEqual(1, result)
        self.assertIn("Full Qualification FALSIFIED", stderr_capture.getvalue())
        self.assertIn("[FAILED] Direct Site assembly build", stderr_capture.getvalue())

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_required_check_cancelled_returns_one(self, mock_runs, mock_jobs) -> None:
        runs, jobs_by_id = build_mock_hierarchy(
            status_overrides={"check": "completed"},
            conclusion_overrides={"check": "cancelled"},
        )
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            result = verify_qualification(
                repo="TakashiSasaki/templates",
                head_sha="0123456789abcdef",
                token="dummy",
                timeout_seconds=1,
                poll_interval_seconds=0,
            )
        self.assertEqual(1, result)
        self.assertIn("Full Qualification FALSIFIED", stderr_capture.getvalue())
        self.assertIn("[CANCELLED] Direct Site browser and PWA check", stderr_capture.getvalue())

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_required_check_skipped_returns_one(self, mock_runs, mock_jobs) -> None:
        runs, jobs_by_id = build_mock_hierarchy(
            status_overrides={"ref_consumer_browser": "completed"},
            conclusion_overrides={"ref_consumer_browser": "skipped"},
        )
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            result = verify_qualification(
                repo="TakashiSasaki/templates",
                head_sha="0123456789abcdef",
                token="dummy",
                timeout_seconds=1,
                poll_interval_seconds=0,
            )
        self.assertEqual(1, result)
        self.assertIn("Full Qualification FALSIFIED", stderr_capture.getvalue())
        self.assertIn("[SKIPPED] Reference consumer browser & PWA acceptance", stderr_capture.getvalue())

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_required_check_pending_then_success_waits_then_passes(
        self, mock_runs, mock_jobs
    ) -> None:
        runs_pending, jobs_pending = build_mock_hierarchy(
            status_overrides={"cross_auth_consumer": "in_progress"},
            conclusion_overrides={"cross_auth_consumer": None},
        )
        runs_success, jobs_success = build_mock_hierarchy(
            status_overrides={"cross_auth_consumer": "completed"},
            conclusion_overrides={"cross_auth_consumer": "success"},
        )

        call_count = 0

        def mock_runs_fn(repo, head_sha, token):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return runs_pending
            return runs_success

        def mock_jobs_fn(repo, run_id, token):
            if call_count == 1:
                return jobs_pending.get(run_id, [])
            return jobs_success.get(run_id, [])

        mock_runs.side_effect = mock_runs_fn
        mock_jobs.side_effect = mock_jobs_fn

        result = verify_qualification(
            repo="TakashiSasaki/templates",
            head_sha="0123456789abcdef",
            token="dummy",
            timeout_seconds=5,
            poll_interval_seconds=0,
        )
        self.assertEqual(0, result)
        self.assertGreaterEqual(call_count, 2)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_pending_until_timeout_reports_timeout_not_test_failure(
        self, mock_runs, mock_jobs
    ) -> None:
        runs, jobs_by_id = build_mock_hierarchy(
            status_overrides={"build": "in_progress"},
            conclusion_overrides={"build": None},
        )
        mock_runs.return_value = runs
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_by_id.get(run_id, [])

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            result = verify_qualification(
                repo="TakashiSasaki/templates",
                head_sha="0123456789abcdef",
                token="dummy",
                timeout_seconds=0,
                poll_interval_seconds=0,
            )
        self.assertEqual(1, result)
        stderr_output = stderr_capture.getvalue()
        self.assertIn("Full Qualification TIMED OUT waiting for: Direct Site assembly build", stderr_output)
        self.assertNotIn("Full Qualification FALSIFIED", stderr_output)

    @patch("scripts.verify_site_full_qualification.fetch_run_jobs")
    @patch("scripts.verify_site_full_qualification.fetch_workflow_runs")
    def test_re_attempted_run_invalidates_cache_and_waits_for_completion(
        self, mock_runs, mock_jobs
    ) -> None:
        cache: dict[tuple[int, int], list[dict]] = {}

        # 1. First iteration: build run is completed (attempt 1)
        runs_completed, jobs_completed = build_mock_hierarchy()
        for r in runs_completed:
            r["run_attempt"] = 1
        mock_runs.return_value = runs_completed
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_completed.get(run_id, [])

        evals, missing = evaluate_suites("TakashiSasaki/templates", "0123456789abcdef", "token", cache)
        self.assertEqual("successful", evals["build"].state)
        # Verify cache contains attempt 1
        build_run_id = next(r["id"] for r in runs_completed if r["path"] == ".github/workflows/build-pages.yml")
        self.assertIn((build_run_id, 1), cache)

        # 2. Second iteration: build run is re-run (attempt 2, in_progress)
        runs_reattempted, jobs_reattempted = build_mock_hierarchy(
            status_overrides={"build": "in_progress"},
            conclusion_overrides={"build": None},
        )
        for r in runs_reattempted:
            r["run_attempt"] = 2
        mock_runs.return_value = runs_reattempted
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_reattempted.get(run_id, [])

        evals, missing = evaluate_suites("TakashiSasaki/templates", "0123456789abcdef", "token", cache)
        # Attempt 1 must be purged, and state must be pending, not stale successful
        self.assertNotIn((build_run_id, 1), cache)
        self.assertEqual("pending", evals["build"].state)

        # 3. Third iteration: attempt 2 completed with failure
        runs_failed, jobs_failed = build_mock_hierarchy(
            status_overrides={"build": "completed"},
            conclusion_overrides={"build": "failure"},
        )
        for r in runs_failed:
            r["run_attempt"] = 2
        mock_runs.return_value = runs_failed
        mock_jobs.side_effect = lambda repo, run_id, token: jobs_failed.get(run_id, [])

        evals, missing = evaluate_suites("TakashiSasaki/templates", "0123456789abcdef", "token", cache)
        self.assertEqual("failed", evals["build"].state)
        self.assertIn((build_run_id, 2), cache)


if __name__ == "__main__":
    unittest.main()
