#!/usr/bin/env python3
"""Site Full Qualification aggregate verification.

Verifies that all L3 full-qualification checks are executed, exact-head bound,
and successful across all independent Site workflows:
- Site Construction CI (build, browser/PWA check, and construction aggregate)
- Provider coexistence (coexistence integration and gate)
- Site reference consumer (composition, candidate build, and browser/PWA acceptance)
- Publication freshness (resolve, composition candidate build, and freshness report)
- Publication materialization and publication contract v4
- Site Composition Playground (projection consumer and explainability/browser)
- Cross-authority acceptance (candidate build and Chromium consumer)
- Website contract and policy validation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, NamedTuple


class RequiredSuite(NamedTuple):
    key: str
    description: str
    workflow_path: str
    job_name: str
    job_name_aliases: tuple[str, ...] = ()


REQUIRED_SUITES: list[RequiredSuite] = [
    RequiredSuite(
        key="build",
        description="Direct Site assembly build",
        workflow_path=".github/workflows/build-pages.yml",
        job_name="build",
    ),
    RequiredSuite(
        key="check",
        description="Direct Site browser and PWA check",
        workflow_path=".github/workflows/build-pages.yml",
        job_name="check",
    ),
    RequiredSuite(
        key="construction_gate",
        description="Site Construction CI validate gate",
        workflow_path=".github/workflows/build-pages.yml",
        job_name="Site Construction CI / validate",
        job_name_aliases=("Site CI / validate",),
    ),
    RequiredSuite(
        key="provider_coexistence",
        description="Validate exact provider coexistence",
        workflow_path=".github/workflows/provider-coexistence.yml",
        job_name="Validate exact provider coexistence",
    ),
    RequiredSuite(
        key="provider_coexistence_gate",
        description="Provider coexistence gate",
        workflow_path=".github/workflows/provider-coexistence.yml",
        job_name="Provider coexistence gate",
    ),
    RequiredSuite(
        key="ref_consumer_composition",
        description="Reference consumer composition validation",
        workflow_path=".github/workflows/reference-consumer.yml",
        job_name="composition",
    ),
    RequiredSuite(
        key="ref_consumer_build",
        description="Reference consumer site build",
        workflow_path=".github/workflows/reference-consumer.yml",
        job_name="build / build",
    ),
    RequiredSuite(
        key="ref_consumer_browser",
        description="Reference consumer browser & PWA acceptance",
        workflow_path=".github/workflows/reference-consumer.yml",
        job_name="browser",
    ),
    RequiredSuite(
        key="pub_freshness_resolve",
        description="Publication freshness resolve",
        workflow_path=".github/workflows/check-publication-freshness.yml",
        job_name="resolve",
    ),
    RequiredSuite(
        key="pub_freshness_build",
        description="Publication freshness candidate build",
        workflow_path=".github/workflows/check-publication-freshness.yml",
        job_name="Build with current Composition HEAD / build",
    ),
    RequiredSuite(
        key="pub_freshness_report",
        description="Publication freshness report",
        workflow_path=".github/workflows/check-publication-freshness.yml",
        job_name="report",
    ),
    RequiredSuite(
        key="pub_materialization",
        description="Publication materialization regressions",
        workflow_path=".github/workflows/publication-materialization.yml",
        job_name="materialization",
    ),
    RequiredSuite(
        key="pub_contract",
        description="Publication contract v4 regressions",
        workflow_path=".github/workflows/publication-contract-v4.yml",
        job_name="contract",
    ),
    RequiredSuite(
        key="cross_auth_build",
        description="Cross-authority candidate build",
        workflow_path=".github/workflows/site-composition-playground-cross-authority.yml",
        job_name="Build exact cross-authority candidate / build",
    ),
    RequiredSuite(
        key="cross_auth_consumer",
        description="Real producer to Chromium consumer",
        workflow_path=".github/workflows/site-composition-playground-cross-authority.yml",
        job_name="Real producer to Chromium consumer",
    ),
    RequiredSuite(
        key="playground_consumer",
        description="Site Composition Playground consumer",
        workflow_path=".github/workflows/site-composition-playground.yml",
        job_name="projection consumer",
    ),
    RequiredSuite(
        key="playground_explain",
        description="Site Composition Playground explainability",
        workflow_path=".github/workflows/site-composition-playground-explain.yml",
        job_name="projection explanations and browser acceptance",
    ),
    RequiredSuite(
        key="validate_website",
        description="Validate website contract",
        workflow_path=".github/workflows/validate-website.yml",
        job_name="validate-website",
    ),
    RequiredSuite(
        key="policy",
        description="Check agent policy",
        workflow_path=".github/workflows/check-agent-policy.yml",
        job_name="policy",
    ),
]

EXTERNAL_WORKFLOW_PATHS: tuple[str, ...] = tuple(dict.fromkeys(s.workflow_path for s in REQUIRED_SUITES))
assert ".github/workflows/site-full-qualification.yml" not in EXTERNAL_WORKFLOW_PATHS, (
    "Site full qualification must not depend on itself"
)


def fetch_workflow_runs(repo: str, head_sha: str, token: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "site-full-qualification-verifier")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            print(f"GitHub API error fetching workflow runs: {exc.code} {exc.reason}", file=sys.stderr)
            raise

        batch = data.get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return runs


def fetch_run_jobs(repo: str, run_id: int, token: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "site-full-qualification-verifier")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            print(f"GitHub API error fetching run jobs for {run_id}: {exc.code} {exc.reason}", file=sys.stderr)
            raise

        batch = data.get("jobs", [])
        if not batch:
            break
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return jobs


class SuiteEvaluation(NamedTuple):
    suite: RequiredSuite
    state: str  # "successful", "pending", "failed", "skipped", "cancelled", "missing"
    status: str | None
    conclusion: str | None
    job_id: int | None
    run_id: int | None
    html_url: str | None
    workflow_path: str


def evaluate_suites(
    repo: str,
    head_sha: str,
    token: str,
    completed_jobs_cache: dict[int, list[dict[str, Any]]],
) -> tuple[dict[str, SuiteEvaluation], list[str]]:
    """Evaluates all 19 suites against exact head workflow runs.

    Returns (evaluations_by_key, missing_external_workflow_paths).
    """
    runs = fetch_workflow_runs(repo, head_sha, token)

    # Group runs by workflow path
    runs_by_path: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        path = r.get("path")
        if path:
            runs_by_path.setdefault(path, []).append(r)

    # Check for missing external workflows
    missing_workflows = [
        path for path in EXTERNAL_WORKFLOW_PATHS if path not in runs_by_path
    ]

    evaluations: dict[str, SuiteEvaluation] = {}

    for suite in REQUIRED_SUITES:
        matching_runs = runs_by_path.get(suite.workflow_path, [])
        if not matching_runs:
            evaluations[suite.key] = SuiteEvaluation(
                suite=suite,
                state="missing",
                status=None,
                conclusion=None,
                job_id=None,
                run_id=None,
                html_url=None,
                workflow_path=suite.workflow_path,
            )
            continue

        # Sort runs: prefer pull_request event, then higher run ID (latest)
        selected_run = sorted(
            matching_runs,
            key=lambda r: (r.get("event") == "pull_request", r.get("id", 0)),
        )[-1]
        run_id = selected_run["id"]
        run_status = selected_run.get("status")

        # Fetch jobs (using cache if run is completed)
        if run_id in completed_jobs_cache:
            jobs = completed_jobs_cache[run_id]
        else:
            jobs = fetch_run_jobs(repo, run_id, token)
            if run_status == "completed":
                completed_jobs_cache[run_id] = jobs

        # Find matching job
        target_names = (suite.job_name,) + suite.job_name_aliases
        matched_job = next((j for j in jobs if j.get("name") in target_names), None)

        if matched_job is None:
            # Job not yet started / queued in workflow
            if run_status in ("queued", "in_progress", "waiting", "pending"):
                evaluations[suite.key] = SuiteEvaluation(
                    suite=suite,
                    state="pending",
                    status="queued",
                    conclusion=None,
                    job_id=None,
                    run_id=run_id,
                    html_url=selected_run.get("html_url"),
                    workflow_path=suite.workflow_path,
                )
            else:
                # Workflow completed without producing the job
                evaluations[suite.key] = SuiteEvaluation(
                    suite=suite,
                    state="missing",
                    status="completed",
                    conclusion="missing",
                    job_id=None,
                    run_id=run_id,
                    html_url=selected_run.get("html_url"),
                    workflow_path=suite.workflow_path,
                )
            continue

        job_status = matched_job.get("status")
        job_conclusion = matched_job.get("conclusion")
        job_id = matched_job.get("id")
        html_url = matched_job.get("html_url")

        if job_status in ("queued", "in_progress", "waiting", "pending") or job_status != "completed":
            state = "pending"
        elif job_conclusion == "success":
            state = "successful"
        elif job_conclusion == "skipped":
            state = "skipped"
        elif job_conclusion == "cancelled":
            state = "cancelled"
        else:
            state = "failed"

        evaluations[suite.key] = SuiteEvaluation(
            suite=suite,
            state=state,
            status=job_status,
            conclusion=job_conclusion,
            job_id=job_id,
            run_id=run_id,
            html_url=html_url,
            workflow_path=suite.workflow_path,
        )

    return evaluations, missing_workflows


def verify_qualification(
    repo: str,
    head_sha: str,
    token: str,
    timeout_seconds: int = 2400,
    poll_interval_seconds: int = 20,
) -> int:
    print(f"Starting Site Full Qualification verification for {repo} at {head_sha}")
    print(f"Required external workflow paths: {len(EXTERNAL_WORKFLOW_PATHS)}")
    print(f"Required L3 check suites: {len(REQUIRED_SUITES)}")
    deadline = time.time() + timeout_seconds
    completed_jobs_cache: dict[int, list[dict[str, Any]]] = {}

    while True:
        try:
            evaluations, missing_workflows = evaluate_suites(
                repo, head_sha, token, completed_jobs_cache
            )
        except Exception as exc:
            print(f"Transient error querying GitHub API: {exc}", file=sys.stderr)
            if time.time() >= deadline:
                print("\n❌ Full Qualification TIMED OUT with API error", file=sys.stderr)
                return 1
            time.sleep(poll_interval_seconds)
            continue

        failed_items = [ev for ev in evaluations.values() if ev.state in ("failed", "skipped", "cancelled")]
        pending_items = [ev for ev in evaluations.values() if ev.state in ("pending", "missing")]
        successful_items = [ev for ev in evaluations.values() if ev.state == "successful"]

        # Fatal failure condition: any required suite has failed, cancelled, or skipped
        if failed_items:
            print("\n❌ Full Qualification FALSIFIED: one or more required L3 checks failed:", file=sys.stderr)
            for ev in failed_items:
                print(
                    f"  - [{ev.state.upper()}] {ev.suite.description} (workflow: {ev.suite.workflow_path}, job: {ev.suite.job_name}): status={ev.status} conclusion={ev.conclusion} url={ev.html_url}",
                    file=sys.stderr,
                )
            if pending_items:
                print("\nPending checks at time of failure:", file=sys.stderr)
                for ev in pending_items:
                    print(f"  - {ev.suite.description} (workflow: {ev.suite.workflow_path}): state={ev.state}", file=sys.stderr)
            return 1

        # Success condition: all 19 suites are successful and no missing external workflows
        if len(successful_items) == len(REQUIRED_SUITES) and not missing_workflows:
            print("\n✅ All required L3 Full Qualification suites COMPLETED and GREEN:")
            print("| Stage / Role | Workflow | Check Run / Job Name | Run ID | Status | Conclusion |")
            print("| --- | --- | --- | --- | --- | --- |")
            for suite in REQUIRED_SUITES:
                ev = evaluations[suite.key]
                print(f"| {suite.description} | {suite.workflow_path} | {suite.job_name} | {ev.run_id} | {ev.status} | {ev.conclusion} |")
            return 0

        # Pending condition: wait for remaining checks
        remaining_descriptions = [ev.suite.description for ev in pending_items]
        if missing_workflows:
            remaining_descriptions.extend([f"workflow {p}" for p in missing_workflows])
        summary = ", ".join(remaining_descriptions[:3])
        if len(remaining_descriptions) > 3:
            summary += f"... (+{len(remaining_descriptions) - 3} more)"
        print(f"[{time.strftime('%X')}] Waiting for {len(remaining_descriptions)} checks to complete: {summary}")

        if time.time() >= deadline:
            joined = ', '.join(remaining_descriptions)
            print(f"\n❌ Full Qualification TIMED OUT waiting for: {joined}", file=sys.stderr)
            return 1

        time.sleep(poll_interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/name)")
    parser.add_argument("--head-sha", required=True, help="Exact PR head SHA")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub API token")
    parser.add_argument("--timeout-seconds", type=int, default=2400, help="Max seconds to wait")
    parser.add_argument("--poll-interval-seconds", type=int, default=20, help="Poll interval in seconds")
    args = parser.parse_args()

    return verify_qualification(
        repo=args.repo,
        head_sha=args.head_sha,
        token=args.token,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
