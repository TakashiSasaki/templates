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
import urllib.request
import urllib.error
from typing import Any

# Suite key -> human description and check-run name match predicate
REQUIRED_SUITES: list[tuple[str, str, Any]] = [
    ("build", "Direct Site assembly build", lambda name: name == "build"),
    ("check", "Direct Site browser and PWA check", lambda name: name == "check"),
    (
        "construction_gate",
        "Site Construction CI validate gate",
        lambda name: name in ("Site Construction CI / validate", "Site CI / validate"),
    ),
    (
        "provider_coexistence",
        "Validate exact provider coexistence",
        lambda name: name == "Validate exact provider coexistence",
    ),
    (
        "provider_coexistence_gate",
        "Provider coexistence gate",
        lambda name: name == "Provider coexistence gate",
    ),
    (
        "ref_consumer_composition",
        "Reference consumer composition validation",
        lambda name: name == "composition",
    ),
    (
        "ref_consumer_build",
        "Reference consumer site build",
        lambda name: name == "build / build",
    ),
    (
        "ref_consumer_browser",
        "Reference consumer browser & PWA acceptance",
        lambda name: name == "browser",
    ),
    (
        "pub_freshness_resolve",
        "Publication freshness resolve",
        lambda name: name == "resolve",
    ),
    (
        "pub_freshness_build",
        "Publication freshness candidate build",
        lambda name: name == "Build with current Composition HEAD / build",
    ),
    (
        "pub_freshness_report",
        "Publication freshness report",
        lambda name: name == "report",
    ),
    (
        "pub_materialization",
        "Publication materialization regressions",
        lambda name: name == "materialization",
    ),
    (
        "pub_contract",
        "Publication contract v4 regressions",
        lambda name: name == "contract",
    ),
    (
        "cross_auth_build",
        "Cross-authority candidate build",
        lambda name: name == "Build exact cross-authority candidate / build",
    ),
    (
        "cross_auth_consumer",
        "Real producer to Chromium consumer",
        lambda name: name == "Real producer to Chromium consumer",
    ),
    (
        "playground_consumer",
        "Site Composition Playground consumer",
        lambda name: name == "projection consumer",
    ),
    (
        "playground_explain",
        "Site Composition Playground explainability",
        lambda name: name == "projection explanations and browser acceptance",
    ),
    (
        "validate_website",
        "Validate website contract",
        lambda name: name == "validate-website",
    ),
    (
        "policy",
        "Check agent policy",
        lambda name: name == "policy",
    ),
]


def fetch_check_runs(repo: str, head_sha: str, token: str) -> list[dict[str, Any]]:
    check_runs: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/commits/{head_sha}/check-runs?per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "site-full-qualification-verifier")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            print(f"GitHub API error fetching check runs: {exc.code} {exc.reason}", file=sys.stderr)
            raise

        runs = data.get("check_runs", [])
        if not runs:
            break
        check_runs.extend(runs)
        if len(runs) < 100:
            break
        page += 1
    return check_runs


def verify_qualification(
    repo: str,
    head_sha: str,
    token: str,
    timeout_seconds: int = 2100,
    poll_interval_seconds: int = 20,
) -> int:
    print(f"Starting Site Full Qualification verification for {repo} at {head_sha}")
    deadline = time.time() + timeout_seconds

    while True:
        try:
            check_runs = fetch_check_runs(repo, head_sha, token)
        except Exception as exc:
            print(f"Transient error fetching check runs: {exc}", file=sys.stderr)
            if time.time() >= deadline:
                return 1
            time.sleep(poll_interval_seconds)
            continue

        matched_results: dict[str, dict[str, Any]] = {}
        all_completed = True
        has_failure = False

        for key, description, predicate in REQUIRED_SUITES:
            # Find the best match among check runs for this exact head
            matches = [cr for cr in check_runs if predicate(cr.get("name", ""))]
            if not matches:
                all_completed = False
                continue

            # Take the latest/most relevant run if multiple (e.g. retried)
            # Prefer completed success over in-progress; prefer in-progress over failure
            best_match = None
            for m in matches:
                if m.get("conclusion") == "success":
                    best_match = m
                    break
            if best_match is None:
                for m in matches:
                    if m.get("status") in ("in_progress", "queued", "waiting", "pending"):
                        best_match = m
                        break
            if best_match is None:
                best_match = matches[-1]

            matched_results[key] = best_match
            status = best_match.get("status")
            conclusion = best_match.get("conclusion")

            if status != "completed":
                all_completed = False
            elif conclusion != "success":
                # Explicit failure
                has_failure = True

        if has_failure:
            print("\n❌ Full Qualification FALSIFIED: one or more required L3 checks failed:", file=sys.stderr)
            for key, description, _ in REQUIRED_SUITES:
                cr = matched_results.get(key)
                if cr and cr.get("conclusion") != "success":
                    print(f"  - {description} ({cr.get('name')}): status={cr.get('status')} conclusion={cr.get('conclusion')} url={cr.get('html_url')}", file=sys.stderr)
            return 1

        if all_completed and len(matched_results) == len(REQUIRED_SUITES):
            print("\n✅ All required L3 Full Qualification suites COMPLETED and GREEN:")
            print("| Stage / Role | Check Run Name | ID | Status | Conclusion |")
            print("| --- | --- | --- | --- | --- |")
            for key, description, _ in REQUIRED_SUITES:
                cr = matched_results[key]
                print(f"| {description} | {cr.get('name')} | {cr.get('id')} | {cr.get('status')} | {cr.get('conclusion')} |")
            return 0

        remaining = [description for key, description, _ in REQUIRED_SUITES if key not in matched_results or matched_results[key].get("status") != "completed"]
        print(f"[{time.strftime('%X')}] Waiting for {len(remaining)} checks to complete: {', '.join(remaining[:3])}{'...' if len(remaining) > 3 else ''}")

        if time.time() >= deadline:
            print(f"\n❌ Full Qualification TIMED OUT waiting for: {', '.join(remaining)}", file=sys.stderr)
            return 1

        time.sleep(poll_interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/name)")
    parser.add_argument("--head-sha", required=True, help="Exact PR head SHA")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub API token")
    parser.add_argument("--timeout-seconds", type=int, default=2100, help="Max seconds to wait")
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
