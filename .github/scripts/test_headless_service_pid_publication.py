#!/usr/bin/env python3
"""Prove atomic, no-replace publication and cleanup on partial PID writes."""

from __future__ import annotations

import errno
import glob
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".github/fixtures/profiles/headless-service/src"
sys.path.insert(0, str(SRC))

from text_stats import current_pid_record, write_pid_record  # noqa: E402


def main() -> int:
    failures: list[str] = []
    record = current_pid_record()

    with tempfile.TemporaryDirectory(prefix="headless-service-pid-publication") as temporary:
        directory = Path(temporary)
        pid_file = directory / "service.pid"
        entered = threading.Event()
        release = threading.Event()
        observed: dict[str, Path] = {}
        writer_error: list[BaseException] = []

        def before_publish(staging: Path, destination: Path) -> None:
            observed["staging"] = staging
            observed["destination"] = destination
            entered.set()
            if not release.wait(5.0):
                raise TimeoutError("publication hold timed out")

        def writer() -> None:
            try:
                write_pid_record(pid_file, record, before_publish=before_publish)
            except BaseException as exc:
                writer_error.append(exc)

        thread = threading.Thread(target=writer)
        thread.start()
        if not entered.wait(5.0):
            failures.append("PID writer did not reach the publication boundary")
            release.set()
        else:
            staging = observed["staging"]
            if observed["destination"] != pid_file:
                failures.append("PID record was published to an unexpected path")
            if pid_file.exists() or pid_file.is_symlink():
                failures.append("final PID pathname became visible before publication")
            expected = (
                __import__("json").dumps(record, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            if staging.read_bytes() != expected:
                failures.append("staging PID record was incomplete before publication")
            if staging.stat().st_mode & 0o777 != 0o600:
                failures.append("staging PID record did not have exact mode 0600")
            release.set()
        thread.join(5.0)
        if thread.is_alive():
            failures.append("PID writer did not finish after publication release")
        if writer_error:
            failures.append(f"PID writer failed: {writer_error[0]}")
        if pid_file.is_file():
            expected = (
                __import__("json").dumps(record, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            if pid_file.read_bytes() != expected:
                failures.append("published PID record content changed")
            if pid_file.stat().st_mode & 0o777 != 0o600:
                failures.append("published PID record did not have exact mode 0600")
        else:
            failures.append("published PID record is missing")
        if glob.glob(str(directory / ".service.pid.*.tmp")):
            failures.append("PID staging entry remained after publication")

    with tempfile.TemporaryDirectory(prefix="headless-service-pid-write-failure") as temporary:
        directory = Path(temporary)
        pid_file = directory / "service.pid"
        first = True

        def partial_write(descriptor: int, data: bytes) -> int:
            nonlocal first
            if first:
                first = False
                os.write(descriptor, data[:1])
                raise OSError(errno.ENOSPC, "injected partial PID-record write")
            return os.write(descriptor, data)

        observed_error: BaseException | None = None
        try:
            write_pid_record(pid_file, record, write_function=partial_write)
        except BaseException as exc:
            observed_error = exc
        if observed_error is None:
            failures.append("injected partial PID-record write did not fail")
        if pid_file.exists() or pid_file.is_symlink():
            failures.append("partial PID record was exposed at the final pathname")
        if glob.glob(str(directory / ".service.pid.*.tmp")):
            failures.append("partial PID staging entry was not removed")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Atomic PID-record publication tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
