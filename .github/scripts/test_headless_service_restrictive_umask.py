#!/usr/bin/env python3
"""Prove the default PID lifecycle survives an inherited umask of 0777."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".github/fixtures/profiles/headless-service"
SERVER = FIXTURE / "service/server.py"
TOKEN = "restrictive-umask-test-token-0123456789-abcdef"


def clean_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(extra)
    return env


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="headless-service-restrictive-umask") as temporary:
        root = Path(temporary)
        runtime = root / "fresh-runtime"
        runtime.mkdir(mode=0o700)
        token_file = root / "token"
        token_file.write_text(TOKEN + "\n", encoding="ascii")
        os.chmod(token_file, 0o600)
        pid_directory = runtime / "tmp"
        pid_file = pid_directory / "text-stats-service.pid"
        stdout_file = root / "stdout.log"
        stderr_file = root / "stderr.log"
        env = clean_env(
            {
                "TEXT_STATS_SERVICE_TOKEN_FILE": str(token_file),
                "TEXT_STATS_SERVICE_PORT": "0",
            }
        )

        def restrictive_umask() -> None:
            os.umask(0o777)

        with stdout_file.open("wb") as stdout_handle, stderr_file.open("wb") as stderr_handle:
            process = subprocess.Popen(
                [sys.executable, str(SERVER)],
                cwd=runtime,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                preexec_fn=restrictive_umask,
            )

        try:
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                diagnostics = stderr_file.read_text(encoding="utf-8", errors="replace")
                if pid_file.is_file() and "text-stats service ready" in diagnostics:
                    break
                if process.poll() is not None:
                    failures.append(
                        "service exited before readiness under umask 0777: "
                        f"status={process.returncode!r}, diagnostics={diagnostics!r}"
                    )
                    break
                time.sleep(0.05)
            else:
                failures.append(
                    "service did not become ready under umask 0777: "
                    f"{stderr_file.read_text(encoding='utf-8', errors='replace')!r}"
                )

            if pid_directory.is_dir():
                mode = pid_directory.stat().st_mode & 0o777
                if mode != 0o700:
                    failures.append(f"expected default PID directory mode 0700, got {mode:04o}")
            else:
                failures.append("default PID directory was not created")

            if pid_file.is_file():
                mode = pid_file.stat().st_mode & 0o777
                if mode != 0o600:
                    failures.append(f"expected PID record mode 0600, got {mode:04o}")
                try:
                    record = json.loads(pid_file.read_text(encoding="utf-8"))
                    if record.get("pid") != process.pid:
                        failures.append("PID record does not identify the service process")
                except Exception as exc:
                    failures.append(f"PID record is unreadable: {exc}")

            stop = subprocess.run(
                [sys.executable, str(SERVER), "--stop"],
                cwd=runtime,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=5.0,
                check=False,
            )
            if stop.returncode != 0 or "Sent TERM" not in stop.stdout:
                failures.append(
                    f"--stop failed under restrictive umask: status={stop.returncode!r}, "
                    f"stdout={stop.stdout!r}, stderr={stop.stderr!r}"
                )
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                failures.append("service did not stop after documented --stop")
                process.kill()
                process.wait(timeout=2.0)

            if pid_file.exists() or pid_file.is_symlink():
                failures.append("PID record remained after graceful shutdown")
            if stdout_file.read_bytes():
                failures.append("service wrote unexpected stdout")
            if "text-stats service stopped" not in stderr_file.read_text(
                encoding="utf-8", errors="replace"
            ):
                failures.append("service did not report graceful shutdown")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2.0)

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Restrictive-umask default-path lifecycle test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
