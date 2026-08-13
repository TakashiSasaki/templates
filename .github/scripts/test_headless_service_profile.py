#!/usr/bin/env python3
"""End-to-end regression harness for the headless-service fixture."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".github/fixtures/profiles/headless-service"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"
EXPECTED_FILES = sorted(
    [
        "RUNTIME.md",
        "SKILL.md",
        "service/server.py",
        "src/text_stats.py",
        "tests/test_service_server.py",
    ]
)


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: float = 120.0,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=clean_env(extra_env),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=stdout,
            stderr=stderr + "command timed out\n",
        )


def copy_fixture(target: Path) -> None:
    shutil.copytree(FIXTURE, target, dirs_exist_ok=True, symlinks=True)


def initialize_git(target: Path) -> None:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        result = run(command, cwd=target, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr}")


def validate(target: Path) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(VALIDATOR), str(target)], cwd=target, timeout=30)


def compile_without_writing(path: Path, label: str) -> str | None:
    try:
        compile(path.read_text(encoding="utf-8"), label, "exec", dont_inherit=True)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return str(exc)
    return None


def load_text_stats(target: Path):
    path = target / "src/text_stats.py"
    spec = importlib.util.spec_from_file_location("headless_profile_text_stats", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load headless text_stats fixture module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_short_read_regressions(target: Path, failures: list[str]) -> None:
    module = load_text_stats(target)
    original_read = module.os.read

    token = target / "short-read-token"
    token_prefix = b"A" * 32 + b"\n"
    token_suffix = b"invalid-extra"
    token.write_bytes(token_prefix + token_suffix)
    os.chmod(token, 0o600)
    chunks = [token_prefix, token_suffix, b""]

    def token_read(_descriptor: int, _size: int) -> bytes:
        return chunks.pop(0) if chunks else b""

    module.os.read = token_read
    try:
        try:
            module.read_token(token)
        except module.ConfigurationError:
            pass
        else:
            failures.append(
                "headless-service token short-read regression: a valid prefix plus trailing bytes was accepted"
            )
    finally:
        module.os.read = original_read

    pid = target / "short-read.pid"
    pid_prefix = json.dumps({"pid": 1, "startTicks": "1"}, separators=(",", ":")).encode() + b"\n"
    pid_suffix = b"trailing-garbage"
    pid.write_bytes(pid_prefix + pid_suffix)
    os.chmod(pid, 0o600)
    chunks = [pid_prefix, pid_suffix, b""]

    def pid_read(_descriptor: int, _size: int) -> bytes:
        return chunks.pop(0) if chunks else b""

    module.os.read = pid_read
    try:
        try:
            module.read_pid_record(pid)
        except module.ConfigurationError:
            pass
        else:
            failures.append(
                "headless-service PID short-read regression: a valid JSON prefix plus trailing bytes was accepted"
            )
    finally:
        module.os.read = original_read


def main() -> int:
    failures: list[str] = []
    actual = sorted(
        path.relative_to(FIXTURE).as_posix()
        for path in FIXTURE.rglob("*")
        if not path.is_dir() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    if actual != EXPECTED_FILES:
        failures.append(
            f"headless-service: expected reduced layout {EXPECTED_FILES!r}, got {actual!r}"
        )

    runtime = (FIXTURE / "RUNTIME.md").read_text(encoding="utf-8")
    for command in (
        "TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/mode-0600-token python service/server.py",
        "python service/server.py --stop",
        "python service/server.py --health",
        "python service/server.py --live",
        "python tests/test_service_server.py",
    ):
        if command not in runtime:
            failures.append(
                f"headless-service runtime: missing documented command {command!r}"
            )

    server_source = (FIXTURE / "service/server.py").read_text(encoding="utf-8")
    for required in (
        "if size < 0:",
        "deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS",
        "def _read1_with_deadline",
        "self.rfile.read1(maximum)",
    ):
        if required not in server_source:
            failures.append(
                f"headless-service request-boundary regression: missing {required!r}"
            )
    for forbidden in (
        "self.rfile.read(length)",
        "self.rfile.read(size)",
        "self.rfile.readline(4097)",
    ):
        if forbidden in server_source:
            failures.append(
                f"headless-service overall-deadline regression: unbounded high-level read remains: {forbidden!r}"
            )

    with tempfile.TemporaryDirectory(prefix="headless-service-profile") as temporary:
        target = Path(temporary) / "fixture"
        copy_fixture(target)
        initialize_git(target)

        validation = validate(target)
        if validation.returncode != 0:
            failures.append(
                "headless-service: expected complete repository validation to pass; "
                f"stdout={validation.stdout!r}, stderr={validation.stderr!r}"
            )

        for relative in (
            "src/text_stats.py",
            "service/server.py",
            "tests/test_service_server.py",
        ):
            diagnostic = compile_without_writing(target / relative, relative)
            if diagnostic is not None:
                failures.append(
                    f"headless-service syntax {relative}: expected success; diagnostic={diagnostic!r}"
                )

        tests = run(
            [sys.executable, "tests/test_service_server.py"],
            cwd=target,
            timeout=120,
        )
        if tests.returncode != 0:
            failures.append(
                "headless-service tests: expected success; "
                f"stdout={tests.stdout!r}, stderr={tests.stderr!r}"
            )

        exercise_short_read_regressions(target, failures)

        token_fifo = target / "token.fifo"
        os.mkfifo(token_fifo, 0o600)
        started = time.monotonic()
        fifo_start = run(
            [sys.executable, "service/server.py"],
            cwd=target,
            timeout=5,
            extra_env={
                "TEXT_STATS_SERVICE_TOKEN_FILE": str(token_fifo),
                "TEXT_STATS_SERVICE_PORT": "0",
                "TEXT_STATS_SERVICE_PID_FILE": str(target / "fifo-token.pid"),
            },
        )
        elapsed = time.monotonic() - started
        if (
            fifo_start.returncode == 0
            or "regular non-symlink" not in fifo_start.stderr
            or elapsed >= 4.0
        ):
            failures.append(
                "headless-service token FIFO guard: expected prompt regular-file rejection; "
                f"status={fifo_start.returncode!r}, stderr={fifo_start.stderr!r}, elapsed={elapsed:.3f}"
            )

        pid_fifo = target / "service.pid.fifo"
        os.mkfifo(pid_fifo, 0o600)
        started = time.monotonic()
        fifo_stop = run(
            [sys.executable, "service/server.py", "--stop"],
            cwd=target,
            timeout=5,
            extra_env={
                "TEXT_STATS_SERVICE_PORT": "4568",
                "TEXT_STATS_SERVICE_PID_FILE": str(pid_fifo),
            },
        )
        elapsed = time.monotonic() - started
        if (
            fifo_stop.returncode == 0
            or "regular non-symlink" not in fifo_stop.stderr
            or elapsed >= 4.0
        ):
            failures.append(
                "headless-service PID FIFO guard: expected prompt regular-file rejection; "
                f"status={fifo_stop.returncode!r}, stderr={fifo_stop.stderr!r}, elapsed={elapsed:.3f}"
            )

        implementation = target / "src/text_stats.py"
        missing = implementation.with_suffix(".py.missing")
        implementation.rename(missing)
        token = target / "token"
        token.write_text("missing-implementation-test-token-1234567890\n", encoding="ascii")
        os.chmod(token, 0o600)
        missing_implementation = run(
            [sys.executable, "service/server.py"],
            cwd=target,
            timeout=5,
            extra_env={
                "TEXT_STATS_SERVICE_TOKEN_FILE": str(token),
                "TEXT_STATS_SERVICE_PORT": "0",
                "TEXT_STATS_SERVICE_PID_FILE": str(target / "missing.pid"),
            },
        )
        if missing_implementation.returncode == 0 or not missing_implementation.stderr.strip():
            failures.append(
                "headless-service missing implementation: expected prompt nonzero failure with diagnostics; "
                f"status={missing_implementation.returncode!r}, stderr={missing_implementation.stderr!r}"
            )
        missing.rename(implementation)

    with tempfile.TemporaryDirectory(prefix="invalid-headless-service-profile") as temporary:
        target = Path(temporary)
        copy_fixture(target)
        (target / "RUNTIME.md").unlink()
        initialize_git(target)
        validation = validate(target)
        if validation.returncode == 0:
            failures.append(
                "headless-service invalid contract: missing RUNTIME.md unexpectedly validates"
            )
        elif "RUNTIME.md" not in validation.stderr:
            failures.append(
                "headless-service invalid contract: expected actionable RUNTIME.md diagnostic; "
                f"stderr={validation.stderr!r}"
            )

    with tempfile.TemporaryDirectory(prefix="invalid-headless-browser-contract") as temporary:
        target = Path(temporary)
        copy_fixture(target)
        (target / "WEB_INTERFACE.md").write_text(
            "# Unsupported browser contract\n", encoding="utf-8"
        )
        initialize_git(target)
        validation = validate(target)
        if validation.returncode == 0:
            failures.append(
                "headless-service browser contract: retained WEB_INTERFACE.md unexpectedly validates"
            )
        elif "WEB_INTERFACE.md" not in validation.stderr:
            failures.append(
                "headless-service browser contract: expected actionable WEB_INTERFACE.md diagnostic; "
                f"stderr={validation.stderr!r}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Headless-service profile fixture tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
