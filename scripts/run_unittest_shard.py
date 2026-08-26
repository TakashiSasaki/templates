#!/usr/bin/env python3
"""Run one deterministic shard of a named repository unittest suite."""

from __future__ import annotations

import argparse
import hashlib
import sys
import unittest
from collections.abc import Iterator, Sequence
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# These are the tests that execute a real Chrome session as part of their
# acceptance boundary. Keep the list at exact unittest-id granularity: many
# other tests describe or unit-test browser evidence without launching Chrome.
REAL_BROWSER_TEST_IDS = frozenset(
    {
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

# PR #471 balanced unittest *counts*, but the post-merge run still measured
# shard runtimes at 154.364 s versus 104.260 s. These two tests accounted for
# roughly 26 s on the slower shard. Keep the general SHA-256 partition stable,
# but move only these measured outliers when the production workflow uses two
# shards. Other shard counts deliberately retain the pure hash assignment.
TWO_SHARD_TIMING_OVERRIDES = {
    "test_composer_generated_material.ComposerGeneratedMaterialTests."
    "test_webapp_apply_generates_and_locks_contract_manifest": 1,
    "test_webapp_auth_productization.WebappAuthenticationProductizationTests."
    "test_realistic_auth_fixture_reaches_transactional_release": 1,
}


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
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
