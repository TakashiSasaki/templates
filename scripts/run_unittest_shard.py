#!/usr/bin/env python3
"""Run one deterministic shard of a named repository unittest suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unittest
from collections.abc import Iterator, Sequence
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TIMING_LOG_PREFIX = "COMPOSITION_UNITTEST_TIMING "
TIMING_SCHEMA_VERSION = 1

# These are the tests that execute a real Chrome session as part of their
# acceptance boundary. Keep the list at exact unittest-id granularity: many
# other tests describe or unit-test browser evidence without launching Chrome.
REAL_BROWSER_TEST_IDS = frozenset(
    {
        "test_pwa_browser_evidence.PwaBrowserEvidenceTests."
        "test_mutable_origin_proves_pwa_browser_evidence_families",
        "test_selected_component_validation.SelectedComponentValidationTests."
        "test_product_release_checks_are_explicitly_deferred",
        "test_task_ledger_walkthrough_browser_acceptance."
        "TaskLedgerWalkthroughBrowserAcceptanceTests."
        "test_walkthrough_reaches_real_browser_product_mode_valid",
        "test_webapp_auth_productization.WebappAuthenticationProductizationTests."
        "test_realistic_auth_fixture_reaches_transactional_release",
        "test_webapp_auth_productization.WebappAuthenticationProductizationTests."
        "test_role_bypass_candidate_fails_release_and_restores_outputs",
        "test_webapp_productization_acceptance.WebappProductizationAcceptanceTests."
        "test_composer_generated_webapp_reaches_revision_bound_product_release",
        "test_webapp_productization_acceptance.WebappProductizationAcceptanceTests."
        "test_revision_digest_and_chronology_binding_fail_closed",
        "test_webapp_productization_bundle_fail_closed."
        "WebappProductizationBundleFailClosedTests."
        "test_bundle_revision_and_artifact_digest_fail_closed",
    }
)
SUITES = ("all", "core", "real-browser")

# PR #478 added two measured two-shard overrides when Chrome-backed tests still
# shared the production shards with the core suite. PR #513 later separated the
# real-browser tests into their own one-shard job, so that historical browser
# override no longer belongs to the production two-shard core suite. Keep only
# the remaining measured core outlier until multi-run per-test timing telemetry
# is available to support a less noisy balancing decision.
TWO_SHARD_TIMING_OVERRIDES = {
    "test_composer_generated_material.ComposerGeneratedMaterialTests."
    "test_webapp_apply_generates_and_locks_contract_manifest": 1,
}


class TimingTextTestResult(unittest.TextTestResult):
    """Collect parent unittest durations without changing unittest semantics."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.test_durations: list[tuple[str, float]] = []
        self._started_ns: dict[int, int] = {}

    def startTest(self, test: unittest.case.TestCase) -> None:
        self._started_ns[id(test)] = time.perf_counter_ns()
        super().startTest(test)

    def stopTest(self, test: unittest.case.TestCase) -> None:
        started_ns = self._started_ns.pop(id(test), None)
        if started_ns is not None:
            duration_seconds = max(
                0.0,
                (time.perf_counter_ns() - started_ns) / 1_000_000_000,
            )
            self.test_durations.append((test.id(), duration_seconds))
        super().stopTest(test)


def iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.case.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def discover_tests(start_dir: Path, pattern: str) -> list[unittest.case.TestCase]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(start_dir), pattern=pattern, top_level_dir=str(start_dir))
    return list(iter_tests(suite))


def select_tests_for_suite(
    tests: Sequence[unittest.case.TestCase], suite_name: str
) -> list[unittest.case.TestCase]:
    if suite_name not in SUITES:
        raise ValueError(f"unknown suite: {suite_name}")
    if suite_name == "all":
        return list(tests)
    if suite_name == "real-browser":
        selected = [test for test in tests if test.id() in REAL_BROWSER_TEST_IDS]
        discovered_ids = {test.id() for test in tests}
        missing = sorted(REAL_BROWSER_TEST_IDS - discovered_ids)
        if missing:
            raise ValueError(
                "real-browser suite contains undiscovered unittest ids: "
                + ", ".join(missing)
            )
        return selected
    return [test for test in tests if test.id() not in REAL_BROWSER_TEST_IDS]


def _pure_hash_shard_index(test_id: str, shard_count: int) -> int:
    digest = hashlib.sha256(test_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def shard_index_for_test_id(test_id: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard count must be at least 1")
    if shard_count == 2 and test_id in TWO_SHARD_TIMING_OVERRIDES:
        return TWO_SHARD_TIMING_OVERRIDES[test_id]
    return _pure_hash_shard_index(test_id, shard_count)


def validate_two_shard_timing_overrides(
    discovered: Sequence[unittest.case.TestCase],
) -> None:
    discovered_ids = {test.id() for test in discovered}
    stale = sorted(set(TWO_SHARD_TIMING_OVERRIDES) - discovered_ids)
    if stale:
        raise ValueError(
            "two-shard timing overrides contain undiscovered unittest ids: "
            + ", ".join(stale)
        )
    browser = sorted(set(TWO_SHARD_TIMING_OVERRIDES) & REAL_BROWSER_TEST_IDS)
    if browser:
        raise ValueError(
            "two-shard timing overrides must not include real-browser unittest ids: "
            + ", ".join(browser)
        )
    redundant = sorted(
        test_id
        for test_id, override in TWO_SHARD_TIMING_OVERRIDES.items()
        if override == _pure_hash_shard_index(test_id, 2)
    )
    if redundant:
        raise ValueError(
            "two-shard timing overrides are redundant with deterministic hashing: "
            + ", ".join(redundant)
        )


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=SUITES,
        default="all",
        help="named test suite to run; defaults to all discovered tests",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="number of deterministic shards",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="zero-based shard index to run",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify discovery/suite/shard invariants without running tests",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be at least 1")
    if not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("--shard-index must be within the shard count")

    discovered = discover_tests(REPOSITORY_ROOT / "tests", "test*.py")
    validate_two_shard_timing_overrides(discovered)
    selected = select_tests_for_suite(discovered, args.suite)
    shard_counts = [0] * args.shard_count
    for test in selected:
        shard_counts[shard_index_for_test_id(test.id(), args.shard_count)] += 1
    print(
        f"Discovered {len(discovered)} unittest instances; selected {len(selected)} "
        f"for suite {args.suite}; deterministic shard counts: {shard_counts}"
    )
    if args.verify_only:
        return 0

    selected_for_shard = [
        test
        for test in selected
        if shard_index_for_test_id(test.id(), args.shard_count) == args.shard_index
    ]
    print(
        f"Running {args.suite} shard {args.shard_index + 1}/{args.shard_count}: "
        f"{len(selected_for_shard)} unittest instances"
    )
    suite = unittest.TestSuite(selected_for_shard)
    runner = unittest.TextTestRunner(verbosity=2, resultclass=TimingTextTestResult)
    result = runner.run(suite)
    if isinstance(result, TimingTextTestResult):
        for line in format_timing_records(
            result.test_durations,
            suite=args.suite,
            shard_count=args.shard_count,
            shard_index=args.shard_index,
        ):
            print(line)
    return 0 if result.wasSuccessful() else 1


def format_timing_records(
    durations: Sequence[tuple[str, float]],
    *,
    suite: str,
    shard_count: int,
    shard_index: int,
) -> list[str]:
    lines: list[str] = []
    for test_id, duration in sorted(durations):
        payload = {
            "schema_version": TIMING_SCHEMA_VERSION,
            "suite": suite,
            "shard_count": shard_count,
            "shard_index": shard_index,
            "test_id": test_id,
            "duration_seconds": round(duration, 9),
        }
        lines.append(
            TIMING_LOG_PREFIX
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
