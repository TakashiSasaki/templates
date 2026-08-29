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
# seven real-browser tests into their own one-shard job, so that historical
# browser override no longer belongs to the production two-shard core suite.
# Keep only the remaining measured core outlier until multi-run per-test timing
# telemetry is available to support a less noisy balancing decision.
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


def format_timing_records(
    timings: Sequence[tuple[str, float]],
    *,
    suite: str,
    shard_count: int,
    shard_index: int,
) -> list[str]:
    """Return stable JSON-line telemetry suitable for later Actions-log aggregation."""
    return [
        TIMING_LOG_PREFIX
        + json.dumps(
            {
                "schema_version": TIMING_SCHEMA_VERSION,
                "suite": suite,
                "shard_count": shard_count,
                "shard_index": shard_index,
                "test_id": test_id,
                "duration_seconds": round(duration_seconds, 9),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for test_id, duration_seconds in sorted(timings, key=lambda item: item[0])
    ]


def iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.case.TestCase]:
    """Yield individual tests from an arbitrarily nested unittest suite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def stable_hash_shard_index(test_id: str, shard_count: int) -> int:
    """Map one stable unittest id to one shard using SHA-256."""
    digest = hashlib.sha256(test_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def shard_index_for_test_id(test_id: str, shard_count: int) -> int:
    """Map one stable unittest id to exactly one deterministic shard."""
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    if shard_count == 2 and test_id in TWO_SHARD_TIMING_OVERRIDES:
        return TWO_SHARD_TIMING_OVERRIDES[test_id]
    return stable_hash_shard_index(test_id, shard_count)


def validate_two_shard_timing_overrides(
    tests: Sequence[unittest.case.TestCase],
) -> None:
    """Fail closed when a production core timing override becomes stale or inert."""
    discovered_ids = {test.id() for test in tests}
    override_ids = set(TWO_SHARD_TIMING_OVERRIDES)

    missing = sorted(override_ids - discovered_ids)
    if missing:
        raise ValueError(
            "two-shard timing overrides reference undiscovered unittest ids: "
            + ", ".join(missing)
        )

    browser_overlap = sorted(override_ids & REAL_BROWSER_TEST_IDS)
    if browser_overlap:
        raise ValueError(
            "two-shard core timing overrides reference real-browser unittest ids: "
            + ", ".join(browser_overlap)
        )

    invalid_targets = sorted(
        test_id
        for test_id, shard_index in TWO_SHARD_TIMING_OVERRIDES.items()
        if shard_index not in {0, 1}
    )
    if invalid_targets:
        raise ValueError(
            "two-shard timing overrides reference invalid shard indexes: "
            + ", ".join(invalid_targets)
        )

    redundant = sorted(
        test_id
        for test_id, shard_index in TWO_SHARD_TIMING_OVERRIDES.items()
        if stable_hash_shard_index(test_id, 2) == shard_index
    )
    if redundant:
        raise ValueError(
            "two-shard timing overrides no longer change stable hash assignment: "
            + ", ".join(redundant)
        )


def discover_tests(start_directory: Path, pattern: str) -> list[unittest.case.TestCase]:
    root = REPOSITORY_ROOT.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(
        str(start_directory.resolve()),
        pattern=pattern,
    )
    return list(iter_tests(suite))


def select_tests_for_suite(
    tests: Sequence[unittest.case.TestCase], suite: str
) -> list[unittest.case.TestCase]:
    """Return one named suite while failing closed on stale browser test ids."""
    if suite not in SUITES:
        raise ValueError(f"unknown unittest suite: {suite}")
    selected = list(tests)
    if suite == "all":
        return selected

    discovered_ids = {test.id() for test in selected}
    missing = sorted(REAL_BROWSER_TEST_IDS - discovered_ids)
    if missing:
        raise ValueError(
            "real-browser suite references undiscovered unittest ids: "
            + ", ".join(missing)
        )

    if suite == "real-browser":
        return [test for test in selected if test.id() in REAL_BROWSER_TEST_IDS]
    return [test for test in selected if test.id() not in REAL_BROWSER_TEST_IDS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-directory",
        type=Path,
        default=Path("tests"),
        help="unittest discovery start directory (default: tests)",
    )
    parser.add_argument(
        "--pattern",
        default="test*.py",
        help="unittest discovery filename pattern (default: test*.py)",
    )
    parser.add_argument(
        "--suite",
        choices=SUITES,
        default="all",
        help="named test suite to shard (default: all)",
    )
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="discover and validate the partition without executing tests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be at least 1")
    if not args.verify_only and args.shard_index is None:
        raise SystemExit("--shard-index is required unless --verify-only is used")
    if args.shard_index is not None and not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("--shard-index must be in [0, shard-count)")

    start_directory = args.start_directory
    if not start_directory.is_absolute():
        start_directory = REPOSITORY_ROOT / start_directory
    discovered = discover_tests(start_directory, args.pattern)
    if not discovered:
        raise SystemExit("unittest discovery produced no tests")
    if args.shard_count == 2:
        try:
            validate_two_shard_timing_overrides(discovered)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    try:
        tests = select_tests_for_suite(discovered, args.suite)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not tests:
        raise SystemExit(f"unittest suite {args.suite!r} produced no tests")

    counts = [0] * args.shard_count
    for test in tests:
        counts[shard_index_for_test_id(test.id(), args.shard_count)] += 1
    if any(count == 0 for count in counts):
        raise SystemExit(f"deterministic partition produced an empty shard: {counts}")

    print(
        f"Discovered {len(discovered)} unittest instances; "
        f"selected {len(tests)} for suite {args.suite}; "
        f"deterministic shard counts: {counts}",
        flush=True,
    )
    if args.verify_only:
        return 0

    selected = [
        test
        for test in tests
        if shard_index_for_test_id(test.id(), args.shard_count) == args.shard_index
    ]
    print(
        f"Running {args.suite} shard {args.shard_index + 1}/{args.shard_count}: "
        f"{len(selected)} unittest instances",
        flush=True,
    )
    result = unittest.TextTestRunner(
        verbosity=2,
        resultclass=TimingTextTestResult,
    ).run(unittest.TestSuite(selected))
    if not isinstance(result, TimingTextTestResult):
        raise RuntimeError("timing result class was not preserved by unittest runner")
    for line in format_timing_records(
        result.test_durations,
        suite=args.suite,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
    ):
        print(line, flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
