from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_policy_preflight import (  # noqa: E402
    EXCLUSIVE_FOCUSED_TESTS,
    FOCUSED_TEST_SPECS,
    FOCUSED_TESTS,
    PARALLEL_EXECUTION_CLASSES,
    PARALLEL_FOCUSED_TESTS,
    FocusedTest,
    check_focused_tests,
    positive_jobs,
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
    """Parallel/process and isolated-workspace tests stay separate from exclusives."""
    parallel_set = set(PARALLEL_FOCUSED_TESTS)
    serial_set = set(EXCLUSIVE_FOCUSED_TESTS)
    all_set = set(FOCUSED_TESTS)

    assert parallel_set.isdisjoint(serial_set), (
        f"Overlap detected between parallel-safe and serial-required: {parallel_set & serial_set}"
    )
    assert parallel_set | serial_set == all_set, (
        f"Partition mismatch: missing {all_set - (parallel_set | serial_set)}"
    )


def test_execution_classes_distinguish_process_workspace_and_exclusive_state() -> None:
    classes = {spec.path: spec.execution_class for spec in FOCUSED_TEST_SPECS}
    assert classes["tests/test_review_scope_selection.py"] == "parallel/process"
    assert classes["tests/test_config_driven_check.py"] == "isolated-workspace"
    assert classes["tests/test_maintainer_entrypoint_workflow.py"] == "exclusive"
    assert all(
        spec.execution_class in {*PARALLEL_EXECUTION_CLASSES, "exclusive"}
        for spec in FOCUSED_TEST_SPECS
    )


def test_canonical_worktree_mutators_remain_exclusive() -> None:
    """Canonical worktree file poisoning must never overlap other test processes."""
    serial_set = set(EXCLUSIVE_FOCUSED_TESTS)

    # Process-local cwd/sys.path mutation is isolated in a loadfile xdist worker.
    assert "tests/test_maintainer_source_closure.py" not in serial_set
    # These tests poison canonical files shared by all workers.
    assert "tests/test_maintainer_entrypoint_workflow.py" in serial_set
    assert "tests/test_maintainer_progressive_disclosure.py" in serial_set
    assert "tests/test_prospective_self_host_qualification_boundary.py" not in serial_set


def test_all_focused_test_files_exist_on_disk() -> None:
    """Verify all declared focused test files actually exist on disk."""
    for spec in FOCUSED_TEST_SPECS:
        path = ROOT / spec.path
        assert path.is_file(), f"Declared focused test file does not exist: {spec.path}"


def test_unclassified_test_addition_fails_closed() -> None:
    """A new focused entry cannot omit its execution safety classification."""
    with pytest.raises(TypeError):
        FocusedTest("tests/test_unclassified.py")  # type: ignore[call-arg]


def test_jobs_must_be_at_least_one() -> None:
    assert positive_jobs("1") == 1
    with pytest.raises(argparse.ArgumentTypeError, match=">= 1"):
        positive_jobs("0")
    with pytest.raises(argparse.ArgumentTypeError, match="integer"):
        positive_jobs("auto")


def test_dynamic_import_without_sys_modules_registration() -> None:
    """Verify run_policy_preflight can be dynamically loaded without being in sys.modules."""
    import importlib.util

    script_path = ROOT / "scripts" / "run_policy_preflight.py"
    spec = importlib.util.spec_from_file_location("isolated_run_policy_preflight", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Ensure it is NOT in sys.modules during execution
    sys.modules.pop("isolated_run_policy_preflight", None)
    spec.loader.exec_module(module)
    assert hasattr(module, "FOCUSED_TEST_SPECS")
    assert len(module.FOCUSED_TEST_SPECS) > 0


# -----------------------------------------------------------------------------
# Execution & Control Flow Tests
# -----------------------------------------------------------------------------


def test_check_focused_tests_executes_budgeted_parallel_then_exclusive_then_evidence() -> None:
    """Verify xdist receives the budget and exclusives execute without workers."""
    calls: list[list[str]] = []

    def mock_run(*args: str) -> None:
        calls.append(list(args))

    with patch("scripts.run_policy_preflight.run", side_effect=mock_run):
        check_focused_tests(jobs=2)

    assert len(calls) == 3

    # Call 1: process/workspace-safe pytest with the assigned worker budget.
    cmd1 = calls[0]
    assert cmd1[0] == sys.executable
    assert cmd1[1:5] == ["-m", "pytest", "-o", "addopts=-q"]
    assert cmd1[5:8] == ["-n", "2", "--dist=loadfile"]
    assert cmd1[8:] == list(PARALLEL_FOCUSED_TESTS)

    # Call 2: exclusive pytest without xdist workers.
    cmd2 = calls[1]
    assert cmd2[0] == sys.executable
    assert cmd2[1:4] == ["-m", "pytest", "-o"]
    assert "-n" not in cmd2
    assert cmd2[4:] == ["addopts=-q", *EXCLUSIVE_FOCUSED_TESTS]

    # Call 3: delivery evidence validation
    cmd3 = calls[2]
    assert cmd3[0] == sys.executable
    assert cmd3[1] == "scripts/check_policy_delivery_evidence.py"


def test_jobs_one_runs_both_focused_groups_without_xdist(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []
    with patch(
        "scripts.run_policy_preflight.run",
        side_effect=lambda *args: calls.append(list(args)),
    ):
        check_focused_tests(jobs=1)
    pytest_calls = [call for call in calls if "pytest" in call]
    assert len(pytest_calls) == 2
    assert all("-n" not in call and "--dist=loadfile" not in call for call in pytest_calls)
    assert all("addopts=-q" in call for call in pytest_calls)
    assert "POLICY_TEST_WORKERS suite=focused requested=1 effective=1" in capsys.readouterr().out


def test_parallel_failure_propagates_and_aborts_phase() -> None:
    """Failure in the parallel-safe group must halt execution before serial tests run."""
    calls: list[list[str]] = []

    def mock_run(*args: str) -> None:
        calls.append(list(args))
        if "-n" in args:
            raise RuntimeError("parallel pytest failure")

    with patch("scripts.run_policy_preflight.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="parallel pytest failure"):
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
