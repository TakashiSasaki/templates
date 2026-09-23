from __future__ import annotations

import subprocess
import threading
import time
from unittest.mock import patch

import pytest

from scripts.run_policy_preflight import CHECKS, PROFILES, exact_head, main, run_fast


def test_compile_occurs_before_parallel_phase() -> None:
    """14.1 Compile PASS occurs before lint/self-check execution."""
    timeline: list[str] = []

    def mock_compile() -> None:
        timeline.append("compile_start")
        time.sleep(0.01)
        timeline.append("compile_end")

    def mock_lint() -> None:
        timeline.append("lint_start")

    def mock_self_check() -> None:
        timeline.append("self_check_start")

    def mock_focused_tests() -> None:
        timeline.append("focused_tests_start")

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    selected = run_fast("head_sha_test", checks=registry)
    assert selected == PROFILES["fast"]

    compile_end_idx = timeline.index("compile_end")
    lint_start_idx = timeline.index("lint_start")
    self_check_start_idx = timeline.index("self_check_start")

    assert compile_end_idx < lint_start_idx
    assert compile_end_idx < self_check_start_idx


def test_lint_and_self_check_share_same_phase_concurrently() -> None:
    """14.2 Prove lint and self-check can be concurrently active."""
    lint_started = threading.Event()
    self_check_started = threading.Event()
    both_active = threading.Event()

    def mock_compile() -> None:
        pass

    def mock_lint() -> None:
        lint_started.set()
        if self_check_started.wait(timeout=2.0):
            both_active.set()

    def mock_self_check() -> None:
        self_check_started.set()
        if lint_started.wait(timeout=2.0):
            both_active.set()

    def mock_focused_tests() -> None:
        pass

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    run_fast("head_sha_test", checks=registry)
    assert both_active.is_set(), "lint and self-check were not active concurrently"


def test_focused_tests_starts_only_after_both_parallel_checks_pass() -> None:
    """14.3 Focused tests start only after both lint and self-check complete."""
    finished: set[str] = set()
    events: list[str] = []

    def mock_compile() -> None:
        pass

    def mock_lint() -> None:
        time.sleep(0.01)
        finished.add("lint")
        events.append("lint_pass")

    def mock_self_check() -> None:
        time.sleep(0.01)
        finished.add("self-check")
        events.append("self_check_pass")

    def mock_focused_tests() -> None:
        assert "lint" in finished, "focused-tests started before lint finished"
        assert "self-check" in finished, "focused-tests started before self-check finished"
        events.append("focused_tests_start")

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    run_fast("head_sha_test", checks=registry)
    assert events.index("focused_tests_start") > events.index("lint_pass")
    assert events.index("focused_tests_start") > events.index("self_check_pass")


def test_lint_failure_blocks_focused_tests() -> None:
    """14.4 Lint failure allows self-check to settle, fails overall, blocks focused tests."""
    self_check_settled = threading.Event()
    focused_tests_called = threading.Event()

    def mock_compile() -> None:
        pass

    def mock_lint() -> None:
        raise RuntimeError("simulated lint failure")

    def mock_self_check() -> None:
        time.sleep(0.02)
        self_check_settled.set()

    def mock_focused_tests() -> None:
        focused_tests_called.set()

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    with pytest.raises(RuntimeError, match="simulated lint failure"):
        run_fast("head_sha_test", checks=registry)

    assert self_check_settled.is_set(), "self-check did not settle after sibling failure"
    assert not focused_tests_called.is_set(), "focused-tests was called after lint failure"


def test_self_check_failure_blocks_focused_tests() -> None:
    """14.5 Self-check failure allows lint to settle, fails overall, blocks focused tests."""
    lint_settled = threading.Event()
    focused_tests_called = threading.Event()

    def mock_compile() -> None:
        pass

    def mock_lint() -> None:
        time.sleep(0.02)
        lint_settled.set()

    def mock_self_check() -> None:
        raise subprocess.CalledProcessError(1, ["agent-policy", "check"])

    def mock_focused_tests() -> None:
        focused_tests_called.set()

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    with pytest.raises(subprocess.CalledProcessError):
        run_fast("head_sha_test", checks=registry)

    assert lint_settled.is_set(), "lint did not settle after sibling failure"
    assert not focused_tests_called.is_set(), "focused-tests was called after self-check failure"


def test_both_parallel_checks_fail_settles_and_reports_both() -> None:
    """14.8 Both parallel checks fail: both settle and both failure details are reported."""

    def mock_compile() -> None:
        pass

    def mock_lint() -> None:
        raise RuntimeError("lint error details")

    def mock_self_check() -> None:
        raise ValueError("self-check error details")

    def mock_focused_tests() -> None:
        pass

    registry = {
        "compile": mock_compile,
        "lint": mock_lint,
        "self-check": mock_self_check,
        "focused-tests": mock_focused_tests,
    }

    with pytest.raises(RuntimeError) as exc_info:
        run_fast("head_sha_test", checks=registry)

    message = str(exc_info.value)
    assert "lint (lint error details)" in message
    assert "self-check (self-check error details)" in message


def test_explicit_check_flag_remains_sequential() -> None:
    """14.6 Explicit --check runs sequentially and does not invoke run_fast."""
    executed_order: list[str] = []

    def mock_lint() -> None:
        executed_order.append("lint")

    def mock_self_check() -> None:
        executed_order.append("self-check")

    custom_checks = dict(CHECKS)
    custom_checks["lint"] = mock_lint
    custom_checks["self-check"] = mock_self_check

    with patch("scripts.run_policy_preflight.CHECKS", custom_checks), patch(
        "scripts.run_policy_preflight.run_fast"
    ) as mock_run_fast:
        rc = main(["fast", "--check", "self-check", "--check", "lint"])
        assert rc == 0
        mock_run_fast.assert_not_called()
        assert executed_order == ["self-check", "lint"]


def test_full_and_ready_profiles_are_unchanged() -> None:
    """14.7 full profile remains sequential and does not invoke run_fast."""
    executed_checks: list[str] = []
    custom_checks = {
        name: (lambda n=name: executed_checks.append(n)) for name in PROFILES["full"]
    }

    with patch("scripts.run_policy_preflight.CHECKS", custom_checks), patch(
        "scripts.run_policy_preflight.run_fast"
    ) as mock_run_fast:
        rc = main(["full"])
        assert rc == 0
        mock_run_fast.assert_not_called()
        assert executed_checks == list(PROFILES["full"])


def test_canonical_fast_profile_markers_and_identity(capsys: pytest.CaptureFixture[str]) -> None:
    """Truthful logging: verify START/PASS markers and final summary order."""
    custom_checks = {
        "compile": lambda: None,
        "lint": lambda: None,
        "self-check": lambda: None,
        "focused-tests": lambda: None,
    }

    current_head = exact_head()
    with patch("scripts.run_policy_preflight.CHECKS", custom_checks):
        rc = main(["fast", "--expected-head", current_head])
        assert rc == 0

    captured = capsys.readouterr()
    stdout = captured.out

    assert f"POLICY_PREFLIGHT_CHECK_START name=compile head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_PASS name=compile head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_START name=lint head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_PASS name=lint head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_START name=self-check head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_PASS name=self-check head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_START name=focused-tests head={current_head}" in stdout
    assert f"POLICY_PREFLIGHT_CHECK_PASS name=focused-tests head={current_head}" in stdout

    expected_pass_line = (
        f"POLICY_PREFLIGHT_PASS profile=fast head={current_head} "
        "checks=compile,lint,focused-tests,self-check"
    )
    assert expected_pass_line in stdout
