#!/usr/bin/env python3
"""End-to-end regression harness for the browser-interface fixture."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".github/fixtures/profiles/browser-interface"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"
EXPECTED_FILES = sorted(
    [
        "RUNTIME.md",
        "SKILL.md",
        "WEB_INTERFACE.md",
        "src/text_stats.py",
        "tests/test_web_server.py",
        "web/server.py",
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
    timeout: float = 90.0,
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
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "command timed out\n",
        )


def is_python_cache(path: Path) -> bool:
    relative = path.relative_to(FIXTURE)
    return "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}


def copy_fixture(target: Path) -> None:
    shutil.copytree(
        FIXTURE,
        target,
        dirs_exist_ok=True,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def initialize_git(target: Path) -> None:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        result = run(command, cwd=target, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr}")


def validate(target: Path) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(VALIDATOR), str(target)], cwd=target, timeout=30)


def compile_without_writing(target: Path, relative: str) -> str | None:
    try:
        source = (target / relative).read_text(encoding="utf-8")
        compile(source, relative, "exec", dont_inherit=True)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return str(exc)
    return None


def main() -> int:
    failures: list[str] = []
    actual = sorted(
        path.relative_to(FIXTURE).as_posix()
        for path in FIXTURE.rglob("*")
        if not path.is_dir() and not is_python_cache(path)
    )
    if actual != EXPECTED_FILES:
        failures.append(
            f"browser-interface: expected reduced layout {EXPECTED_FILES!r}, got {actual!r}"
        )

    runtime = (FIXTURE / "RUNTIME.md").read_text(encoding="utf-8")
    for command in (
        "TEXT_STATS_WEB_ENABLED=1 python web/server.py",
        "python web/server.py --stop",
        "python web/server.py --health",
        "python tests/test_web_server.py",
    ):
        if command not in runtime:
            failures.append(
                f"browser-interface runtime: missing documented command {command!r}"
            )

    with tempfile.TemporaryDirectory(prefix="browser-interface-profile") as temporary:
        target = Path(temporary) / "fixture"
        copy_fixture(target)
        initialize_git(target)

        validation = validate(target)
        if validation.returncode != 0:
            failures.append(
                "browser-interface: expected complete repository validation to pass; "
                f"stdout={validation.stdout!r}, stderr={validation.stderr!r}"
            )

        for relative in (
            "src/text_stats.py",
            "web/server.py",
            "tests/test_web_server.py",
        ):
            diagnostic = compile_without_writing(target, relative)
            if diagnostic is not None:
                failures.append(
                    f"browser-interface syntax {relative}: diagnostic={diagnostic!r}"
                )

        tests = run(
            [sys.executable, "tests/test_web_server.py"],
            cwd=target,
            timeout=90,
        )
        if tests.returncode != 0:
            failures.append(
                "browser-interface tests: expected success; "
                f"stdout={tests.stdout!r}, stderr={tests.stderr!r}"
            )

        post_validation = validate(target)
        if post_validation.returncode != 0:
            failures.append(
                "browser-interface: syntax/tests mutated the fixture into an invalid repository; "
                f"stdout={post_validation.stdout!r}, stderr={post_validation.stderr!r}"
            )

        caches = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
            and ("__pycache__" in path.relative_to(target).parts or path.suffix in {".pyc", ".pyo"})
        )
        if caches:
            failures.append(
                f"browser-interface: Python validation left bytecode cache artifacts: {caches!r}"
            )

        implementation = target / "src/text_stats.py"
        missing = implementation.with_suffix(".py.missing")
        implementation.rename(missing)
        missing_implementation = run(
            [sys.executable, "web/server.py"],
            cwd=target,
            timeout=5,
            extra_env={
                "TEXT_STATS_WEB_ENABLED": "1",
                "TEXT_STATS_WEB_PORT": "0",
                "TEXT_STATS_WEB_PID_FILE": str(target / "missing.pid"),
            },
        )
        if missing_implementation.returncode == 0 or not missing_implementation.stderr.strip():
            failures.append(
                "browser-interface missing implementation: expected prompt nonzero failure with diagnostics; "
                f"status={missing_implementation.returncode!r}, "
                f"stderr={missing_implementation.stderr!r}"
            )
        missing.rename(implementation)

    with tempfile.TemporaryDirectory(prefix="invalid-browser-interface-profile") as temporary:
        target = Path(temporary)
        copy_fixture(target)
        (target / "WEB_INTERFACE.md").unlink()
        initialize_git(target)
        validation = validate(target)
        if validation.returncode == 0:
            failures.append(
                "browser-interface invalid contract: missing WEB_INTERFACE.md unexpectedly validates"
            )
        elif "WEB_INTERFACE.md" not in validation.stderr:
            failures.append(
                "browser-interface invalid contract: expected actionable WEB_INTERFACE.md diagnostic; "
                f"stderr={validation.stderr!r}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Browser-interface profile fixture tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
