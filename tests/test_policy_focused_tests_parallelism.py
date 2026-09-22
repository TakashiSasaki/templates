from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_policy_preflight import (  # noqa: E402
    FOCUSED_TEST_SPECS,
    FOCUSED_TESTS,
    PARALLEL_FOCUSED_TEST_WORKERS,
    PARALLEL_SAFE_FOCUSED_TESTS,
    SERIAL_FOCUSED_TESTS,
    FocusedTest,
    check_focused_tests,
)

# -----------------------------------------------------------------------------
# Classification & Partitioning Invariants
# -----------------------------------------------------------------------------


def test_every_focused_test_is_classified_exactly_once() -> None:
    """Every focused test in FOCUSED_TESTS originates from FOCUSED_TEST_SPECS without duplicates."""
    spec_paths = [spec.path for spec in FOCUSED_TEST_SPECS]
    assert len(spec_paths) == len(set(spec_paths)), "Duplicate test paths in FOCUSED_TEST_SPECS"
    assert tuple(spec_paths) == FOCUSED_TESTS


def test_focused_test_partition_is_disjoint_and_complete() -> None:
    """Parallel-safe and serial-required sets must be disjoint and cover all focused tests."""
    parallel_set = set(PARALLEL_SAFE_FOCUSED_TESTS)
    serial_set = set(SERIAL_FOCUSED_TESTS)
    all_set = set(FOCUSED_TESTS)

    assert parallel_set.isdisjoint(serial_set), (
        f"Overlap detected between parallel-safe and serial-required: {parallel_set & serial_set}"
    )
    assert parallel_set | serial_set == all_set, (
        f"Partition mismatch: missing {all_set - (parallel_set | serial_set)}"
    )


def test_parallel_worker_count_is_strictly_bounded_to_two() -> None:
    """Explicitly verify that maximum pytest concurrency is 2."""
    assert PARALLEL_FOCUSED_TEST_WORKERS == 2


def test_known_adversarial_and_global_state_tests_remain_serial() -> None:
    """Tests that poison worktree files or mutate global working directory must be serial."""
    serial_set = set(SERIAL_FOCUSED_TESTS)

    # 1. test_maintainer_source_closure mutates os.chdir and sys.path
    assert "tests/test_maintainer_source_closure.py" in serial_set
    # 2. test_maintainer_entrypoint_workflow poisons entrypoint/sibling files in canonical worktree
    assert "tests/test_maintainer_entrypoint_workflow.py" in serial_set
    # 3. test_maintainer_progressive_disclosure poisons reference files in canonical worktree
    assert "tests/test_maintainer_progressive_disclosure.py" in serial_set


def test_all_focused_test_files_exist_on_disk() -> None:
    """Verify all declared focused test files actually exist on disk."""
    for spec in FOCUSED_TEST_SPECS:
        path = ROOT / spec.path
        assert path.is_file(), f"Declared focused test file does not exist: {spec.path}"


def test_unclassified_test_addition_fails_closed() -> None:
    """If a test path is added to FOCUSED_TESTS without a corresponding FocusedTest spec, fail."""
    arbitrary_spec = FocusedTest("tests/test_unclassified.py", parallel_safe=True)
    assert hasattr(arbitrary_spec, "path")
    assert hasattr(arbitrary_spec, "parallel_safe")
    assert hasattr(arbitrary_spec, "reason")


# -----------------------------------------------------------------------------
# Execution & Control Flow Tests
# -----------------------------------------------------------------------------


def test_check_focused_tests_executes_parallel_then_serial_then_evidence() -> None:
    """Verify execution topology: parallel pytest (-n 2) -> serial pytest -> delivery evidence."""
    calls: list[list[str]] = []

    def mock_run(*args: str) -> None:
        calls.append(list(args))

    with patch("scripts.run_policy_preflight.run", side_effect=mock_run):
        check_focused_tests()

    assert len(calls) == 3

    # Call 1: parallel-safe pytest with -n 2
    cmd1 = calls[0]
    assert cmd1[0] == sys.executable
    assert cmd1[1:5] == ["-m", "pytest", "-n", "2"]
    assert cmd1[5:] == list(PARALLEL_SAFE_FOCUSED_TESTS)

    # Call 2: serial-required pytest without -n
    cmd2 = calls[1]
    assert cmd2[0] == sys.executable
    assert cmd2[1:3] == ["-m", "pytest"]
    assert "-n" not in cmd2
    assert cmd2[3:] == list(SERIAL_FOCUSED_TESTS)

    # Call 3: delivery evidence validation
    cmd3 = calls[2]
    assert cmd3[0] == sys.executable
    assert cmd3[1] == "scripts/check_policy_delivery_evidence.py"


def test_parallel_failure_propagates_and_aborts_phase() -> None:
    """Failure in the parallel-safe group must halt execution before serial tests run."""
    calls: list[list[str]] = []

    def mock_run(*args: str) -> None:
        calls.append(list(args))
        if "-n" in args:
            raise RuntimeError("parallel-safe pytest failure")

    with patch("scripts.run_policy_preflight.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="parallel-safe pytest failure"):
            check_focused_tests()

    # Only parallel was attempted; serial and evidence must NOT have been called
    assert len(calls) == 1
    assert "-n" in calls[0]


def test_serial_failure_propagates_and_aborts_phase() -> None:
    """Failure in the serial group must halt execution before delivery evidence check."""
    calls: list[list[str]] = []

    def mock_run(*args: str) -> None:
        calls.append(list(args))
        if "-m" in args and "pytest" in args and "-n" not in args:
            raise RuntimeError("serial-required pytest failure")

    with patch("scripts.run_policy_preflight.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="serial-required pytest failure"):
            check_focused_tests()

    # Parallel and serial were attempted; evidence check must NOT have run
    assert len(calls) == 2
    assert "-n" in calls[0]
    assert "-n" not in calls[1]


def test_missing_focused_test_file_fails_closed_before_execution() -> None:
    """Missing focused test file on disk aborts before executing any tests."""
    with patch(
        "scripts.run_policy_preflight.FOCUSED_TESTS",
        ("tests/nonexistent_test_suite_xyz.py",),
    ):
        with pytest.raises(RuntimeError, match="focused Policy test suites are missing"):
            check_focused_tests()
