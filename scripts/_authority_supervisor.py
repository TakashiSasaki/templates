#!/usr/bin/env python3
"""Run one authority command and own its complete Linux descendant lifecycle.

Each invocation gets a separate supervisor process. That process alone becomes
a Linux child subreaper, so waitpid(-1) can never consume another authority
worker's children. Process-group signals stay scoped to the authority command;
adopted children that detach from that group are found through standard procfs
process records and reaped by their own supervisor. This does not depend on the
optional ``/proc/<pid>/task/<pid>/children`` interface.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

NATURAL_EXIT_GRACE_SECONDS = 0.25
TERMINATION_GRACE_SECONDS = 1.0
REAP_GRACE_SECONDS = 1.0
POLL_INTERVAL_SECONDS = 0.01
_STOP_REQUESTED = False


def _enable_linux_child_subreaper() -> bool:
    if sys.platform != "linux":
        return False

    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.restype = ctypes.c_int
    current = ctypes.c_int()
    if prctl(37, ctypes.byref(current), 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    if not current.value and prctl(36, 1, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    return True


def _parent_pid_from_proc_stat(value: str) -> int:
    """Read PPID from ``/proc/<pid>/stat``, whose command field may contain spaces."""

    closing_parenthesis = value.rfind(")")
    if closing_parenthesis < 0:
        raise ValueError("proc stat record has no command-field terminator")
    fields = value[closing_parenthesis + 1 :].split()
    if len(fields) < 2:
        raise ValueError("proc stat record has no parent PID")
    return int(fields[1])


def _direct_child_pids(
    *, proc_root: Path | None = None, parent_pid: int | None = None
) -> tuple[int, ...] | None:
    """List direct children by scanning standard Linux ``/proc/*/stat`` records.

    The kernel's per-process ``children`` file is optional. ``stat`` is part of
    the ordinary procfs process record and exposes each process's parent PID.
    Return ``None`` when procfs cannot be read completely enough to establish
    this supervisor's child set; callers then fail closed.
    """

    root = proc_root if proc_root is not None else Path("/proc")
    expected_parent = os.getpid() if parent_pid is None else parent_pid
    child_pids: list[int] = []
    try:
        for entry in root.iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                # The parenthesized ``comm`` field is arbitrary process-name
                # bytes, and adopted descendants may have changed credentials.
                # Preserve the command bytes losslessly and identify ownership
                # by PPID rather than the process's current UID.
                stat_record = (entry / "stat").read_bytes().decode(
                    "ascii", errors="surrogateescape"
                )
            except (FileNotFoundError, ProcessLookupError):
                # A process can exit between enumerating its PID and reading it.
                continue
            except PermissionError:
                # A same-user process should be readable; otherwise cleanup is
                # not able to prove that it found every adopted child.
                return None
            except OSError:
                return None
            try:
                recorded_parent = _parent_pid_from_proc_stat(stat_record)
            except (UnicodeError, ValueError):
                return None
            if recorded_parent == expected_parent:
                child_pids.append(int(entry.name))
    except OSError:
        return None
    return tuple(sorted(child_pids))


def _reap_available_children() -> bool:
    """Reap every exited child; return true only when none remain."""

    while True:
        try:
            child_pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        except InterruptedError:
            continue
        if child_pid == 0:
            return False


def _wait_for_children(timeout: float) -> bool:
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        if _reap_available_children():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))


def _signal_adopted_children(signum: int, timeout: float) -> bool:
    """Signal and reap this invocation's adopted children, including detachments."""

    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        children = _direct_child_pids()
        if children is None:
            return False
        for child_pid in children:
            try:
                os.kill(child_pid, signum)
            except ProcessLookupError:
                pass
        if _reap_available_children():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))


def _signal_authority_group(process_group_id: int, signum: int) -> None:
    try:
        if os.name == "posix":
            os.killpg(process_group_id, signum)
    except ProcessLookupError:
        pass


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group(process_group_id: int, timeout: float) -> bool:
    if os.name != "posix":
        return True
    deadline = time.monotonic() + max(timeout, 0.0)
    while _process_group_exists(process_group_id):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))
    return True


def _finish_authority_tree(
    process: subprocess.Popen[bytes],
    *,
    subreaper_enabled: bool,
    allow_natural_exit: bool,
) -> bool:
    process_group_id = process.pid

    if process.poll() is None:
        _signal_authority_group(process_group_id, signal.SIGTERM)
        try:
            process.wait(timeout=TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _signal_authority_group(process_group_id, signal.SIGKILL)
            try:
                process.wait(timeout=REAP_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=REAP_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    return False
    try:
        process.wait(timeout=REAP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        return False

    if subreaper_enabled:
        if allow_natural_exit and _wait_for_children(NATURAL_EXIT_GRACE_SECONDS):
            return True

        _signal_authority_group(process_group_id, signal.SIGTERM)
        if _signal_adopted_children(
            signal.SIGTERM, TERMINATION_GRACE_SECONDS
        ) and _wait_for_children(REAP_GRACE_SECONDS):
            return True

        _signal_authority_group(process_group_id, signal.SIGKILL)
        if not _signal_adopted_children(signal.SIGKILL, REAP_GRACE_SECONDS):
            return False
        return _wait_for_children(REAP_GRACE_SECONDS)

    # Non-Linux POSIX systems can terminate the invocation group, but their
    # coordinator cannot adopt or reap detached grandchildren equivalently.
    _signal_authority_group(process_group_id, signal.SIGTERM)
    if _wait_for_process_group(process_group_id, TERMINATION_GRACE_SECONDS):
        return True
    _signal_authority_group(process_group_id, signal.SIGKILL)
    return _wait_for_process_group(process_group_id, REAP_GRACE_SECONDS)


def _request_stop(_signum: int, _frame: object) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def main(argv: list[str] | None = None) -> int:
    global _STOP_REQUESTED
    _STOP_REQUESTED = False
    args = sys.argv[1:] if argv is None else argv
    try:
        separator = args.index("--")
    except ValueError:
        print("authority supervisor requires -- before the command", file=sys.stderr)
        return 2
    command = args[separator + 1 :]
    if not command:
        print("authority supervisor requires a command", file=sys.stderr)
        return 2

    if argv is None:
        signal.signal(signal.SIGTERM, _request_stop)
        signal.signal(signal.SIGINT, _request_stop)

    try:
        subreaper_enabled = _enable_linux_child_subreaper()
    except OSError as exc:
        print(f"Linux child-subreaper support is required: {exc}", file=sys.stderr)
        return 125

    if subreaper_enabled and _direct_child_pids() is None:
        print(
            "Linux procfs process records are required for descendant cleanup; "
            "refusing to launch the authority",
            file=sys.stderr,
        )
        return 125

    if _STOP_REQUESTED:
        return 124

    try:
        process = subprocess.Popen(
            command,
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        print(f"authority spawn failed: {exc}", file=sys.stderr)
        return 126

    try:
        while process.poll() is None and not _STOP_REQUESTED:
            time.sleep(POLL_INTERVAL_SECONDS)
        cleanup_complete = _finish_authority_tree(
            process,
            subreaper_enabled=subreaper_enabled,
            allow_natural_exit=not _STOP_REQUESTED,
        )
    except BaseException as exc:
        print(f"authority lifecycle failed: {exc}", file=sys.stderr)
        _signal_authority_group(process.pid, signal.SIGKILL)
        try:
            process.kill()
            process.wait(timeout=REAP_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if subreaper_enabled:
            _signal_adopted_children(signal.SIGKILL, REAP_GRACE_SECONDS)
            _wait_for_children(REAP_GRACE_SECONDS)
        return 125
    if not cleanup_complete:
        print(
            "authority descendant cleanup did not complete within its bounded deadline",
            file=sys.stderr,
        )
        return 125
    if _STOP_REQUESTED:
        return 124

    return process.returncode if process.returncode >= 0 else 128 - process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
