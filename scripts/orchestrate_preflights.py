#!/usr/bin/env python3
"""Orchestrate canonical local preflights across repository authorities.

Provides a thin execution and normalization layer over existing authority-owned preflights:
1. Discovers and binds canonical per-authority commands and exact worktree heads.
2. Executes validations locally with finite timeouts and captured detailed logs.
3. Produces bounded, structured machine-readable results (<= 8 KiB) and a concise summary table.
4. Preserves authority boundaries: does NOT re-implement or alter authority validation semantics.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_SUMMARY_BYTES = 8192
DEFAULT_TIMEOUT_SECONDS = 300
SUPERVISOR_CLEANUP_TIMEOUT_SECONDS = 4.0
SUPERVISOR_KILL_TIMEOUT_SECONDS = 1.0
SUPERVISOR_STOPPED_CLEANLY_EXIT_CODE = 124

# Canonical authority definitions based on live authority contracts
CANONICAL_CONFIGS: dict[str, dict[str, Any]] = {
    "policy": {
        "worktree_rel": "policy",
        "entrypoint": "scripts/run_policy_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "composition": {
        "worktree_rel": "composition",
        "entrypoint": "scripts/run_composition_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "modeling": {
        "worktree_rel": "modeling",
        "entrypoint": "tools/qualify.py",
        "default_args": [],
        "supports_expected_head": True,
    },
    "integration": {
        "worktree_rel": "integration",
        "entrypoint": "scripts/run_integration_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "site": {
        "worktree_rel": "site",
        "entrypoint": "scripts/run_site_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
}

ALL_AUTHORITIES = tuple(CANONICAL_CONFIGS.keys())

@dataclass
class AuthorityRunResult:
    authority: str
    status: str  # PASS, FAIL, TIMEOUT, UNAVAILABLE, NOT_RUN
    head_sha: str
    command: list[str]
    working_directory: str
    elapsed_seconds: float
    exit_code: int | None
    allocated_workers: int
    allocation_batch: int
    log_file: str | None = None
    failure_excerpt: str | None = None


COORDINATOR_INTERRUPT_POLL_SECONDS = 0.25
_COORDINATOR_INTERRUPTED = threading.Event()
_COORDINATOR_INTERRUPT_SIGNAL: int | None = None
_ACTIVE_SUPERVISORS: set[subprocess.Popen[str]] = set()
_ACTIVE_SUPERVISORS_LOCK = threading.Lock()


class CoordinatorInterrupted(Exception):
    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"coordinator interrupted by signal {signum}")


def _request_supervisor_stop(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGTERM)
    except (OSError, ValueError):
        pass


def _register_supervisor(process: subprocess.Popen[str]) -> None:
    with _ACTIVE_SUPERVISORS_LOCK:
        _ACTIVE_SUPERVISORS.add(process)
    if _COORDINATOR_INTERRUPTED.is_set():
        _request_supervisor_stop(process)


def _unregister_supervisor(process: subprocess.Popen[str]) -> None:
    with _ACTIVE_SUPERVISORS_LOCK:
        _ACTIVE_SUPERVISORS.discard(process)


def _handle_coordinator_signal(signum: int, _frame: object) -> None:
    global _COORDINATOR_INTERRUPT_SIGNAL
    _COORDINATOR_INTERRUPT_SIGNAL = signum
    _COORDINATOR_INTERRUPTED.set()
    with _ACTIVE_SUPERVISORS_LOCK:
        supervisors = tuple(_ACTIVE_SUPERVISORS)
    for supervisor in supervisors:
        _request_supervisor_stop(supervisor)
    raise CoordinatorInterrupted(signum)


def _install_coordinator_signal_handlers() -> dict[int, object]:
    _COORDINATOR_INTERRUPTED.clear()
    old_handlers = {}
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        signum = getattr(signal, name, None)
        if signum is not None:
            old_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _handle_coordinator_signal)
    return old_handlers


def _restore_coordinator_signal_handlers(old_handlers: dict[int, object]) -> None:
    global _COORDINATOR_INTERRUPT_SIGNAL
    for signum, handler in old_handlers.items():
        signal.signal(signum, handler)
    _COORDINATOR_INTERRUPTED.clear()
    _COORDINATOR_INTERRUPT_SIGNAL = None
    with _ACTIVE_SUPERVISORS_LOCK:
        _ACTIVE_SUPERVISORS.clear()


def allocate_worker_batches(
    authorities: Sequence[str], global_jobs: int
) -> tuple[tuple[tuple[str, int], ...], ...]:
    """Make a deterministic allocation plan whose every batch fits the budget."""

    if global_jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {global_jobs}")
    selected = tuple(authorities)
    if not selected:
        raise ValueError("at least one authority must be selected")
    if len(selected) != len(set(selected)):
        raise ValueError("authority selection contains duplicates")

    batches: list[tuple[tuple[str, int], ...]] = []
    for start in range(0, len(selected), global_jobs):
        members = selected[start : start + global_jobs]
        base, remainder = divmod(global_jobs, len(members))
        batch = tuple(
            (authority, base + (index < remainder))
            for index, authority in enumerate(members)
        )
        if sum(workers for _, workers in batch) > global_jobs:
            raise AssertionError("worker allocation exceeded the global budget")
        batches.append(batch)
    return tuple(batches)


def _get_git_head(worktree: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except Exception:
        return None


def _decode_captured_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _supervisor_process_options() -> dict[str, bool | int]:
    if os.name == "posix":
        return {"start_new_session": True}
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {}


def _close_authority_supervisor_pipes(
    process: subprocess.Popen[str],
) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def _stop_authority_supervisor(
    process: subprocess.Popen[str],
) -> tuple[str, str, bool]:
    """Ask the per-invocation supervisor to finalize, with a bounded fallback."""

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except (OSError, ValueError):
        pass

    stdout = ""
    stderr = ""
    communication_failed = False
    try:
        stdout, stderr = process.communicate(
            timeout=SUPERVISOR_CLEANUP_TIMEOUT_SECONDS
        )
        return (
            stdout,
            stderr,
            process.returncode is not None
            and process.returncode >= 0
            and process.returncode != 125,
        )
    except subprocess.TimeoutExpired as timeout_error:
        stdout = _decode_captured_output(timeout_error.output)
        stderr = _decode_captured_output(timeout_error.stderr)
    except Exception as exc:
        # Stop reading unusable streams, but leave the supervisor alive long
        # enough to handle the stop signal and reap its separate authority tree.
        communication_failed = True
        stderr = f"supervisor cleanup communication failed: {exc}"
        _close_authority_supervisor_pipes(process)
        try:
            process.wait(timeout=SUPERVISOR_CLEANUP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        except Exception as wait_error:
            stderr = (
                f"{stderr}\nsupervisor cleanup wait failed: {wait_error}"
            )
        else:
            # Once the reporting pipes are closed, only the supervisor's
            # explicit stop-and-clean exit code proves descendant cleanup.
            return (
                stdout,
                stderr,
                process.returncode == SUPERVISOR_STOPPED_CLEANLY_EXIT_CODE,
            )

    # communicate() already waited for the supervisor's cleanup deadline, or
    # the supervisor failed to exit during the bounded wait above. Force stop
    # is now the last resort and is reported as incomplete cleanup.
    try:
        if os.name == "posix":
            # The supervisor has its own session. Its authority command is
            # finalized by that supervisor in a separate process group.
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ValueError):
        pass

    if communication_failed:
        try:
            process.wait(timeout=SUPERVISOR_KILL_TIMEOUT_SECONDS)
        except Exception as wait_error:
            stderr = f"{stderr}\nsupervisor wait after kill failed: {wait_error}"
        return stdout, stderr, False

    try:
        final_stdout, final_stderr = process.communicate(
            timeout=SUPERVISOR_KILL_TIMEOUT_SECONDS
        )
        return final_stdout or stdout, final_stderr or stderr, False
    except subprocess.TimeoutExpired as kill_error:
        stdout = _decode_captured_output(kill_error.output) or stdout
        stderr = _decode_captured_output(kill_error.stderr) or stderr
    except Exception as exc:
        detail = f"supervisor cleanup communication failed after kill: {exc}"
        stderr = f"{stderr}\n{detail}".strip()
        _close_authority_supervisor_pipes(process)

    try:
        process.wait(timeout=SUPERVISOR_KILL_TIMEOUT_SECONDS)
    except Exception as wait_error:
        detail = f"supervisor wait after kill failed: {wait_error}"
        stderr = f"{stderr}\n{detail}".strip()

    return stdout, stderr, False


def run_single_preflight(
    authority: str,
    repo_root: Path,
    expected_heads: dict[str, str] | None = None,
    tier_overrides: dict[str, list[str]] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    log_dir: Path | None = None,
    python_bin: str | None = None,
    allocated_workers: int = 1,
    allocation_batch: int = 1,
) -> AuthorityRunResult:
    """Execute canonical preflight for a single authority and return normalized result."""
    if allocated_workers < 1:
        raise ValueError(f"allocated_workers must be at least 1, got {allocated_workers}")
    py_exec = python_bin or sys.executable
    cfg = CANONICAL_CONFIGS.get(authority)
    if not cfg:
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="unknown",
            command=[],
            working_directory=str(repo_root),
            elapsed_seconds=0.0,
            exit_code=None,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            failure_excerpt=f"unknown authority: {authority}",
        )

    worktree = repo_root / cfg["worktree_rel"]
    if not worktree.is_dir():
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="missing",
            command=[],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            failure_excerpt=f"worktree directory does not exist: {worktree}",
        )

    actual_head = _get_git_head(worktree)
    if not actual_head:
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="missing",
            command=[],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            failure_excerpt=f"failed to obtain git rev-parse HEAD from: {worktree}",
        )

    # Check expected head if specified
    if expected_heads and authority in expected_heads:
        expected = expected_heads[authority]
        if actual_head != expected:
            return AuthorityRunResult(
                authority=authority,
                status="FAIL",
                head_sha=actual_head,
                command=[],
                working_directory=str(worktree),
                elapsed_seconds=0.0,
                exit_code=2,
                allocated_workers=allocated_workers,
                allocation_batch=allocation_batch,
                failure_excerpt=(
                    f"head mismatch for {authority}: expected {expected}, "
                    f"observed {actual_head}"
                ),
            )

    script_path = worktree / cfg["entrypoint"]
    if not script_path.is_file():
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha=actual_head,
            command=[str(script_path)],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            failure_excerpt=f"canonical preflight entrypoint not found: {script_path}",
        )

    # Build command
    args = (
        tier_overrides.get(authority, cfg["default_args"])
        if tier_overrides
        else cfg["default_args"]
    )
    cmd = [py_exec, str(script_path), *args]

    if expected_heads and authority in expected_heads and cfg["supports_expected_head"]:
        cmd.extend(["--expected-head", expected_heads[authority]])
    cmd.extend(["--jobs", str(allocated_workers)])

    start_time = time.monotonic()
    log_file_path: Path | None = None
    log_write_error: str | None = None
    if log_dir:
        log_file_path = log_dir / f"{authority}.log"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log_write_error = (
                f"failed to create authority log directory {log_dir}: {exc}"
            )

    proc: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    timed_out = False
    execution_error: Exception | None = None
    cleanup_complete = True
    cleanup_failure: str | None = None
    coordinator_interrupted = False

    supervisor_path = Path(__file__).with_name("_authority_supervisor.py")
    supervisor_cmd = [py_exec, str(supervisor_path), "--", *cmd]
    try:
        if _COORDINATOR_INTERRUPTED.is_set():
            return AuthorityRunResult(
                authority=authority,
                status="FAIL",
                head_sha=actual_head,
                command=cmd,
                working_directory=str(worktree),
                elapsed_seconds=0.0,
                exit_code=128 + (_COORDINATOR_INTERRUPT_SIGNAL or 1),
                allocated_workers=allocated_workers,
                allocation_batch=allocation_batch,
                log_file=str(log_file_path) if log_file_path else None,
                failure_excerpt="coordinator interrupted before authority launch",
            )
        proc = subprocess.Popen(
            supervisor_cmd,
            cwd=worktree,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_supervisor_process_options(),
        )
        _register_supervisor(proc)
        deadline = time.monotonic() + timeout
        while True:
            if _COORDINATOR_INTERRUPTED.is_set():
                coordinator_interrupted = True
                stdout, stderr, cleanup_complete = _stop_authority_supervisor(proc)
                if not cleanup_complete:
                    cleanup_failure = (
                        "authority supervisor did not complete bounded descendant cleanup"
                    )
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                stdout, stderr, cleanup_complete = _stop_authority_supervisor(proc)
                if not cleanup_complete:
                    cleanup_failure = (
                        "authority supervisor did not complete bounded descendant cleanup"
                    )
                break
            try:
                stdout, stderr = proc.communicate(
                    timeout=min(COORDINATOR_INTERRUPT_POLL_SECONDS, remaining)
                )
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception as exc:
                execution_error = exc
                stdout, stderr, cleanup_complete = _stop_authority_supervisor(proc)
                if not cleanup_complete:
                    cleanup_failure = (
                        "authority supervisor did not complete bounded descendant cleanup"
                    )
                break
    except Exception as exc:
        if execution_error is None:
            execution_error = exc
    finally:
        if proc is not None:
            _unregister_supervisor(proc)

    elapsed = round(time.monotonic() - start_time, 2)
    full_output = f"=== STDOUT ===\n{stdout}\n=== STDERR ===\n{stderr}\n"
    if timed_out:
        full_output += f"TIMEOUT after {timeout} seconds\n"
    if cleanup_failure:
        full_output += f"PROCESS CLEANUP\n{cleanup_failure}\n"

    if log_file_path:
        try:
            log_file_path.write_text(full_output, encoding="utf-8")
        except OSError as exc:
            write_error = f"failed to write authority log {log_file_path}: {exc}"
            log_write_error = (
                f"{log_write_error}; {write_error}"
                if log_write_error
                else write_error
            )

    if coordinator_interrupted:
        failure = "coordinator interrupted; authority supervisor cleanup was requested"
        if cleanup_failure:
            failure = f"{failure}; {cleanup_failure}"
        return AuthorityRunResult(
            authority=authority,
            status="FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=128 + (_COORDINATOR_INTERRUPT_SIGNAL or 1),
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt=failure,
        )

    if log_write_error:
        details = [log_write_error]
        if timed_out:
            details.append(f"execution exceeded {timeout}s timeout limit")
        if execution_error is not None:
            details.append(f"subprocess execution failed: {execution_error}")
        if cleanup_failure:
            details.append(cleanup_failure)
        if proc is not None and proc.returncode not in (None, 0):
            details.append(f"authority supervisor exited with {proc.returncode}")
        return AuthorityRunResult(
            authority=authority,
            status="TIMEOUT" if timed_out else "FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=(
                None
                if timed_out
                else proc.returncode
                if proc is not None and proc.returncode not in (None, 0)
                else 1
            ),
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path),
            failure_excerpt="; ".join(details),
        )

    if timed_out:
        failure = f"execution exceeded {timeout}s timeout limit"
        if cleanup_failure:
            failure = f"{failure}; {cleanup_failure}"
        return AuthorityRunResult(
            authority=authority,
            status="TIMEOUT",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=None,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt=failure,
        )

    if execution_error is not None:
        failure = f"subprocess execution failed with error: {execution_error}"
        if cleanup_failure:
            failure = f"{failure}; {cleanup_failure}"
        return AuthorityRunResult(
            authority=authority,
            status="FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=1,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt=failure,
        )

    if proc is None:
        return AuthorityRunResult(
            authority=authority,
            status="FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=1,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt="subprocess was not started",
        )

    if not cleanup_complete:
        combined = stderr.strip() or stdout.strip()
        excerpt = cleanup_failure or "authority descendant cleanup failed"
        if combined:
            excerpt = f"{combined}\n{excerpt}"
        return AuthorityRunResult(
            authority=authority,
            status="FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=proc.returncode if proc.returncode not in (None, 0) else 1,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt=excerpt,
        )

    if proc.returncode == 0:
        return AuthorityRunResult(
            authority=authority,
            status="PASS",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=0,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
            log_file=str(log_file_path) if log_file_path else None,
        )

    # Extract concise failure excerpt (last ~10 lines of stderr/stdout).
    combined = stderr.strip() or stdout.strip()
    lines = combined.splitlines()
    excerpt = "\n".join(lines[-10:]) if len(lines) > 10 else combined
    return AuthorityRunResult(
        authority=authority,
        status="FAIL",
        head_sha=actual_head,
        command=cmd,
        working_directory=str(worktree),
        elapsed_seconds=elapsed,
        exit_code=proc.returncode,
        allocated_workers=allocated_workers,
        allocation_batch=allocation_batch,
        log_file=str(log_file_path) if log_file_path else None,
        failure_excerpt=excerpt,
    )


def orchestrate_preflights(
    authorities: Sequence[str] | None = None,
    repo_root: Path | None = None,
    expected_heads: dict[str, str] | None = None,
    tier_overrides: dict[str, list[str]] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    global_jobs: int = 2,
    log_dir: Path | None = None,
    python_bin: str | None = None,
) -> dict[str, Any]:
    """Orchestrate canonical preflights across specified authorities."""
    if global_jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {global_jobs}")
    selected_authorities = list(ALL_AUTHORITIES if authorities is None else authorities)
    if not selected_authorities:
        raise ValueError("at least one authority must be selected")
    unknown_authorities = [
        authority
        for authority in selected_authorities
        if authority not in CANONICAL_CONFIGS
    ]
    if unknown_authorities:
        raise ValueError(f"unknown authority selection: {unknown_authorities}")
    allocation_batches = allocate_worker_batches(selected_authorities, global_jobs)
    root = (repo_root or Path.cwd()).resolve()
    invocation_id = uuid.uuid4().hex
    invocation_log_dir = log_dir / invocation_id if log_dir else None

    max_active_workers = max(
        (sum(workers for _, workers in batch) for batch in allocation_batches),
        default=0,
    )
    max_authority_concurrency = max(
        (len(batch) for batch in allocation_batches), default=0
    )
    print(
        f"PREFLIGHT_WORKER_BUDGET requested={global_jobs} "
        f"effective_allocation={max_active_workers} "
        f"max_authorities={max_authority_concurrency} run_id={invocation_id}",
        file=sys.stderr,
        flush=True,
    )
    for batch_number, batch in enumerate(allocation_batches, start=1):
        total = sum(workers for _, workers in batch)
        print(
            f"PREFLIGHT_WORKER_ALLOCATION batch={batch_number} total={total} "
            + " ".join(f"{authority}={workers}" for authority, workers in batch),
            file=sys.stderr,
            flush=True,
        )

    start_wall = time.monotonic()
    results: list[AuthorityRunResult] = []
    for batch_number, batch in enumerate(allocation_batches, start=1):
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            future_to_authority = {
                executor.submit(
                    run_single_preflight,
                    authority,
                    repo_root=root,
                    expected_heads=expected_heads,
                    tier_overrides=tier_overrides,
                    timeout=timeout,
                    log_dir=invocation_log_dir,
                    python_bin=python_bin,
                    allocated_workers=workers,
                    allocation_batch=batch_number,
                ): authority
                for authority, workers in batch
            }
            for future in concurrent.futures.as_completed(future_to_authority):
                results.append(future.result())
    auth_order = {auth: idx for idx, auth in enumerate(selected_authorities)}
    results.sort(key=lambda result: auth_order.get(result.authority, 999))

    total_wall = round(time.monotonic() - start_wall, 2)

    # Classify overall status
    statuses = {r.status for r in results}
    if results and all(s == "PASS" for s in statuses):
        overall_status = "PASSED"
    elif any(s in ("FAIL", "TIMEOUT") for s in statuses):
        overall_status = "FAILED"
    else:
        overall_status = "PARTIAL"

    # Format concise summary table
    summary_lines = []
    for r in results:
        head_display = r.head_sha[:8] if len(r.head_sha) >= 8 else r.head_sha
        summary_lines.append(
            f"{r.authority:<12} {r.status:<6} {head_display} ({r.elapsed_seconds}s)"
        )
    summary_table = "\n".join(summary_lines)

    result_data: dict[str, Any] = {
        "schema_version": 2,
        "kind": "preflight-orchestration-result",
        "overall_status": overall_status,
        "is_validation_evidence_only": True,
        "may_establish_acceptance": False,
        "total_wall_clock_seconds": total_wall,
        "run_id": invocation_id,
        "worker_budget": {
            "requested_jobs": global_jobs,
            "max_active_allocated_workers": max_active_workers,
            "max_authority_processes": max_authority_concurrency,
            "allocation_batches": [
                {
                    "batch": batch_number,
                    "authorities": [
                        {"authority": authority, "workers": workers}
                        for authority, workers in batch
                    ],
                }
                for batch_number, batch in enumerate(allocation_batches, start=1)
            ],
        },
        "summary_table": summary_table,
        "authorities": [asdict(r) for r in results],
    }

    # Verify bounded summary size <= MAX_SUMMARY_BYTES
    dumped = json.dumps(result_data, indent=2)
    if len(dumped.encode("utf-8")) > MAX_SUMMARY_BYTES:
        for auth_dict in result_data["authorities"]:
            if (
                auth_dict.get("failure_excerpt")
                and len(auth_dict["failure_excerpt"]) > 300
            ):
                auth_dict["failure_excerpt"] = (
                    auth_dict["failure_excerpt"][:300] + "... (truncated)"
                )

    return result_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "authorities",
        nargs="*",
        default=ALL_AUTHORITIES,
        help=f"authorities to run (default: all {list(ALL_AUTHORITIES)})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="path to repository workspace root (default: current directory)",
    )
    parser.add_argument(
        "--expected-heads-json",
        help="optional path to JSON mapping authority -> expected SHA",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"timeout in seconds per authority (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=2,
        help=(
            "global simultaneous test-worker budget (default: 2); each authority's "
            "explicit local --jobs allocation shares this limit"
        ),
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="optional directory to store full stdout/stderr per authority",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output machine-readable JSON instead of text summary table",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    unknown_authorities = [
        authority
        for authority in args.authorities
        if authority not in CANONICAL_CONFIGS
    ]
    if unknown_authorities:
        parser.error(f"unknown authority selection: {unknown_authorities}")

    if args.jobs < 1:
        parser.error(f"--jobs must be at least 1, got {args.jobs}")

    expected_heads: dict[str, str] | None = None
    if args.expected_heads_json:
        expected_heads = json.loads(
            Path(args.expected_heads_json).read_text(encoding="utf-8")
        )

    old_handlers = _install_coordinator_signal_handlers()
    try:
        res = orchestrate_preflights(
            authorities=args.authorities,
            repo_root=args.repo_root,
            expected_heads=expected_heads,
            timeout=args.timeout,
            global_jobs=args.jobs,
            log_dir=args.log_dir,
        )
    except CoordinatorInterrupted as exc:
        sys.stderr.write(
            f"coordinator interrupted by {signal.Signals(exc.signum).name}; "
            "active authority supervisors were asked to stop\n"
        )
        return 128 + exc.signum
    finally:
        _restore_coordinator_signal_handlers(old_handlers)

    if args.json:
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
    else:
        sys.stdout.write(res["summary_table"] + "\n")
        if res["overall_status"] != "PASSED":
            for a in res["authorities"]:
                if a["status"] != "PASS" and a.get("failure_excerpt"):
                    sys.stderr.write(
                        f"\n[{a['authority']} {a['status']}]:\n{a['failure_excerpt']}\n"
                    )

    return 0 if res["overall_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
