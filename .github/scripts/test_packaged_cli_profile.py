#!/usr/bin/env python3
"""End-to-end regression harness for the packaged CLI fixture."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".github/fixtures/profiles/packaged-cli"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"
EXPECTED_FILES = sorted(
    [
        "CLI_INTERFACE.md",
        "INTERFACES.md",
        "RUNTIME.md",
        "SKILL.md",
        "bin/text-stat",
        "pyproject.toml",
        "requirements-build.lock",
        "src/text_stat/__init__.py",
        "src/text_stat/cli.py",
        "tests/test_text_stat.py",
    ]
)


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def run(
    command: list[str],
    *,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    stdout=None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=clean_env(extra_env),
        input=stdin,
        stdout=stdout if stdout is not None else subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def text(result: subprocess.CompletedProcess) -> tuple[str, str]:
    stdout = result.stdout.decode("utf-8", "replace") if isinstance(result.stdout, bytes) else ""
    stderr = result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else ""
    return stdout, stderr


def require_success(label: str, result: subprocess.CompletedProcess, failures: list[str]) -> None:
    if result.returncode != 0:
        stdout, stderr = text(result)
        failures.append(
            f"{label}: status={result.returncode!r}, stdout={stdout!r}, stderr={stderr!r}"
        )


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def installed_command(root: Path) -> Path:
    return root / ("Scripts/text-stat.exe" if os.name == "nt" else "bin/text-stat")


def copy_fixture(target: Path) -> None:
    shutil.copytree(FIXTURE, target, dirs_exist_ok=True, symlinks=True)


def initialize_git(target: Path) -> None:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        completed = run(command, cwd=target)
        if completed.returncode != 0:
            _, stderr = text(completed)
            raise RuntimeError(f"{' '.join(command)} failed: {stderr}")


def validate(target: Path) -> subprocess.CompletedProcess:
    return run([sys.executable, str(VALIDATOR), str(target)], cwd=target)


def required_json_fields(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("contractVersion") != "1" or payload.get("ok") is not True:
        return False
    result = payload.get("result")
    return (
        isinstance(result, dict)
        and all(type(result.get(key)) is int for key in ("bytes", "lines", "words"))
    )


def main() -> int:
    failures: list[str] = []
    inventory = sorted(
        path.relative_to(FIXTURE).as_posix()
        for path in FIXTURE.rglob("*")
        if not path.is_dir()
    )
    if inventory != EXPECTED_FILES:
        failures.append(
            f"packaged-cli: expected reduced layout {EXPECTED_FILES!r}, got {inventory!r}"
        )

    pyproject = tomllib.loads((FIXTURE / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject.get("project", {}).get("version")
    init_text = (FIXTURE / "src/text_stat/__init__.py").read_text(encoding="utf-8")
    if version != "1.0.0" or 'VERSION = "1.0.0"' not in init_text:
        failures.append("packaged-cli: pyproject version and text_stat.VERSION must both be 1.0.0")
    if pyproject.get("project", {}).get("scripts", {}).get("text-stat") != "text_stat.cli:main":
        failures.append("packaged-cli: pyproject must expose text-stat = text_stat.cli:main")
    if pyproject.get("project", {}).get("dependencies") != []:
        failures.append("packaged-cli: runtime dependency list must remain empty")
    lock_lines = [
        line.strip()
        for line in (FIXTURE / "requirements-build.lock").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if lock_lines != ["setuptools==75.8.0", "wheel==0.45.1"]:
        failures.append("packaged-cli: build-tool lock must contain the exact reviewed pins")

    with tempfile.TemporaryDirectory(prefix="packaged-cli-profile") as temporary:
        target = Path(temporary) / "fixture"
        copy_fixture(target)
        initialize_git(target)
        require_success("complete repository validation", validate(target), failures)

        syntax = run(
            [
                sys.executable,
                "-m",
                "py_compile",
                "bin/text-stat",
                "src/text_stat/__init__.py",
                "src/text_stat/cli.py",
                "tests/test_text_stat.py",
            ],
            cwd=target,
        )
        require_success("Python syntax validation", syntax, failures)
        require_success(
            "packaged CLI unit tests",
            run([sys.executable, "tests/test_text_stat.py"], cwd=target),
            failures,
        )

        input_path = target / "input.txt"
        input_path.write_bytes(b"one two\n")
        inplace = run(
            [sys.executable, "bin/text-stat", "--output", "json", "input.txt"],
            cwd=target,
        )
        require_success("in-place structured output", inplace, failures)
        inplace_stdout, inplace_stderr = text(inplace)
        if inplace.returncode == 0:
            try:
                inplace_payload = json.loads(inplace_stdout)
            except json.JSONDecodeError as exc:
                failures.append(f"in-place JSON is invalid: {exc}")
                inplace_payload = None
            if not required_json_fields(inplace_payload):
                failures.append("in-place JSON omits required contract fields")
            if inplace_stderr:
                failures.append(f"in-place JSON emitted stderr: {inplace_stderr!r}")

        additive = json.loads(inplace_stdout) if inplace.returncode == 0 else {}
        if isinstance(additive.get("result"), dict):
            additive["result"]["futureField"] = "ignored"
        if not required_json_fields(additive):
            failures.append("additive result field compatibility regression failed")

        build_env = target / ".build-venv"
        require_success(
            "create build environment",
            run([sys.executable, "-m", "venv", str(build_env)], cwd=target),
            failures,
        )
        build_python = venv_python(build_env)
        if build_python.is_file():
            require_success(
                "install pinned build tools",
                run(
                    [
                        str(build_python),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--requirement",
                        "requirements-build.lock",
                    ],
                    cwd=target,
                ),
                failures,
            )
            require_success(
                "build wheel",
                run(
                    [
                        str(build_python),
                        "-m",
                        "pip",
                        "wheel",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--no-deps",
                        "--no-build-isolation",
                        "--wheel-dir",
                        "dist",
                        ".",
                    ],
                    cwd=target,
                ),
                failures,
            )

        wheel_files = list((target / "dist").glob("text_stat-1.0.0-*.whl")) if (target / "dist").is_dir() else []
        if len(wheel_files) != 1:
            failures.append(f"packaged-cli: expected exactly one 1.0.0 wheel, got {wheel_files!r}")

        install_env = target / ".local/venv"
        require_success(
            "create local install environment",
            run([sys.executable, "-m", "venv", str(install_env)], cwd=target),
            failures,
        )
        install_python = venv_python(install_env)
        if install_python.is_file() and wheel_files:
            require_success(
                "offline local wheel installation",
                run(
                    [
                        str(install_python),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--no-index",
                        "--find-links",
                        "dist",
                        "text-stat==1.0.0",
                    ],
                    cwd=target,
                ),
                failures,
            )

        command = installed_command(install_env)
        if not command.is_file():
            failures.append(f"packaged-cli: installed text-stat command is missing: {command}")
        else:
            version_run = run([str(command), "--version"], cwd=target)
            require_success("installed version command", version_run, failures)
            version_stdout, version_stderr = text(version_run)
            if version_stdout != "1.0.0\n" or version_stderr:
                failures.append(
                    f"installed version mismatch: stdout={version_stdout!r}, stderr={version_stderr!r}"
                )

            installed_json = run([str(command), "--output", "json", "input.txt"], cwd=target)
            require_success("installed structured output", installed_json, failures)
            installed_stdout, installed_stderr = text(installed_json)
            if installed_stdout != inplace_stdout or installed_stderr != inplace_stderr:
                failures.append("installed and in-place structured output differ")

            invalid = target / "invalid.bin"
            invalid.write_bytes(b"\xff")
            invalid_run = run([str(command), str(invalid)], cwd=target)
            _, invalid_stderr = text(invalid_run)
            if invalid_run.returncode != 2 or "input is not valid UTF-8" not in invalid_stderr:
                failures.append("installed command does not preserve invalid-UTF-8 exit semantics")

            if os.name != "nt" and Path("/dev/full").exists():
                with open("/dev/full", "wb", buffering=0) as full:
                    output_failure = run([str(command), "input.txt"], cwd=target, stdout=full)
                if output_failure.returncode != 5:
                    _, output_stderr = text(output_failure)
                    failures.append(
                        f"installed output failure must return 5; status={output_failure.returncode!r}, "
                        f"stderr={output_stderr!r}"
                    )

        broken = Path(temporary) / "broken"
        copy_fixture(broken)
        (broken / "CLI_INTERFACE.md").unlink()
        initialize_git(broken)
        broken_validation = validate(broken)
        broken_stderr = text(broken_validation)[1]
        actionable_cli_boundary = (
            "CLI_INTERFACE.md" in broken_stderr
            or "Detailed caller behavior:" in broken_stderr
            or "route 'installed human CLI command'" in broken_stderr
            or "route 'stable in-place CLI launcher'" in broken_stderr
        )
        if broken_validation.returncode == 0:
            failures.append("packaged-cli: missing CLI_INTERFACE.md unexpectedly validates")
        elif not actionable_cli_boundary:
            failures.append(
                "packaged-cli: missing CLI_INTERFACE.md lacks an actionable CLI-contract diagnostic: "
                f"{broken_stderr!r}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Packaged CLI profile fixture tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
