#!/usr/bin/env python3
"""Exercise the optional runtime authority for a script-assisted fixture."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / ".github/fixtures/profiles/script-assisted-runtime"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"
EXPECTED_FILES = sorted(
    ["RUNTIME.md", "SKILL.md", "scripts/normalize.py", "tests/test_normalize.py"]
)


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env.pop("GIT_INDEX_FILE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def copy_fixture(directory: Path) -> None:
    shutil.copytree(FIXTURE_ROOT, directory, dirs_exist_ok=True, symlinks=True)


def run_validator(directory: Path) -> subprocess.CompletedProcess[str]:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        result = run(command, cwd=directory)
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr}")
    return run([sys.executable, str(VALIDATOR), str(directory)], cwd=directory)


def validate_without_reindex(directory: Path) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(VALIDATOR), str(directory)], cwd=directory)


def source_snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.relative_to(directory).parts[0] != ".git"
    }


def compile_without_writing(path: Path, relative: str) -> str | None:
    try:
        source = path.read_text(encoding="utf-8")
        compile(source, relative, "exec", dont_inherit=True)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return str(exc)
    return None


def main() -> int:
    failures: list[str] = []
    actual_files = sorted(
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*")
        if not path.is_dir()
    )
    if actual_files != EXPECTED_FILES:
        failures.append(
            "script-assisted-runtime: expected reduced layout "
            f"{EXPECTED_FILES!r}, got {actual_files!r}"
        )

    runtime = (FIXTURE_ROOT / "RUNTIME.md").read_text(encoding="utf-8")
    for required_text in (
        "Selection status: SELECTED",
        "| Runtime | CPython |",
        "| Minimum runtime version | 3.12 |",
        "| Project manifest | NONE |",
        "| Lockfile policy | NONE |",
        "| Source layout | `scripts/normalize.py` and `tests/test_normalize.py` |",
        "| Run in place | `python scripts/normalize.py INPUT OUTPUT` |",
        "| Test | `python tests/test_normalize.py` |",
        "| Build/package | NOT APPLICABLE |",
    ):
        if required_text not in runtime:
            failures.append(
                "script-assisted-runtime: missing runtime authority "
                f"{required_text!r}"
            )

    helper_source = (FIXTURE_ROOT / "scripts/normalize.py").read_text(encoding="utf-8")
    if "output_path.write_bytes(normalized.encode(\"utf-8\"))" not in helper_source:
        failures.append(
            "script-assisted-runtime: helper output must use byte writes to preserve LF bytes on Windows"
        )
    if "os.path.samefile(input_path, output_path)" not in helper_source:
        failures.append(
            "script-assisted-runtime: helper must reject output aliases before writing"
        )

    with tempfile.TemporaryDirectory(prefix="script-assisted-runtime-profile") as temporary:
        directory = Path(temporary)
        copy_fixture(directory)
        validation = run_validator(directory)
        if validation.returncode != 0:
            failures.append(
                "script-assisted-runtime: expected complete repository validation "
                f"to pass; diagnostics={validation.stderr.strip()!r}"
            )

        before_commands = source_snapshot(directory)
        for relative in ("scripts/normalize.py", "tests/test_normalize.py"):
            diagnostic = compile_without_writing(directory / relative, relative)
            if diagnostic is not None:
                failures.append(
                    f"script-assisted-runtime syntax {relative}: expected success; "
                    f"diagnostic={diagnostic!r}"
                )

        fixture_test = run([sys.executable, "tests/test_normalize.py"], cwd=directory)
        if not (
            fixture_test.returncode == 0
            and fixture_test.stdout == "Line normalization helper tests passed.\n"
            and fixture_test.stderr == ""
        ):
            failures.append(
                "script-assisted-runtime test command: expected executable validation success; "
                f"status={fixture_test.returncode!r}, stdout={fixture_test.stdout!r}, "
                f"stderr={fixture_test.stderr!r}"
            )

        after_commands = source_snapshot(directory)
        if after_commands != before_commands:
            failures.append(
                "script-assisted-runtime: syntax/test commands mutated the concrete Skill fixture"
            )
        post_validation = validate_without_reindex(directory)
        if not (
            post_validation.returncode == 0
            and post_validation.stderr == ""
            and "Agent Skill repository structure and profile contracts are valid."
            in post_validation.stdout
        ):
            failures.append(
                "script-assisted-runtime: fixture became invalid after syntax/test commands; "
                f"status={post_validation.returncode!r}, stderr={post_validation.stderr!r}"
            )

        input_path = directory / "input.txt"
        input_path.write_bytes(b"alpha  \r\nbeta\t\r\n")
        input_before = input_path.read_bytes()
        helper = run(
            [sys.executable, "scripts/normalize.py", "input.txt", "output.txt"],
            cwd=directory,
        )
        output_path = directory / "output.txt"
        output = output_path.read_bytes() if output_path.is_file() else None
        if not (
            helper.returncode == 0
            and helper.stdout == "output.txt\n"
            and helper.stderr == ""
            and output == b"alpha\nbeta\n"
            and input_path.read_bytes() == input_before
        ):
            failures.append(
                "script-assisted-runtime helper: expected deterministic output without input mutation; "
                f"status={helper.returncode!r}, stdout={helper.stdout!r}, "
                f"stderr={helper.stderr!r}, output={output!r}"
            )

        alias_factories: dict[str, Callable[[Path, Path], None]] = {
            "hard-link": lambda source, destination: os.link(source, destination),
            "symbolic-link": lambda source, destination: destination.symlink_to(source.name),
        }
        for description, create_alias in alias_factories.items():
            alias_input = directory / f"{description}-input.txt"
            alias_output = directory / f"{description}-output.txt"
            alias_input.write_bytes(b"immutable  \r\n")
            alias_input_before = alias_input.read_bytes()
            try:
                create_alias(alias_input, alias_output)
            except OSError as exc:
                failures.append(f"could not create {description} fixture: {exc}")
                continue
            helper = run(
                [
                    sys.executable,
                    "scripts/normalize.py",
                    alias_input.name,
                    alias_output.name,
                ],
                cwd=directory,
            )
            if not (
                helper.returncode == 2
                and helper.stdout == ""
                and helper.stderr
                == "input and output must refer to different files\n"
                and alias_input.read_bytes() == alias_input_before
                and alias_output.read_bytes() == alias_input_before
            ):
                failures.append(
                    "script-assisted-runtime helper: expected "
                    f"{description} output alias rejection without input mutation; "
                    f"status={helper.returncode!r}, stdout={helper.stdout!r}, "
                    f"stderr={helper.stderr!r}, input={alias_input.read_bytes()!r}"
                )

        (directory / "invalid.txt").write_bytes(b"\xff")
        helper = run(
            [
                sys.executable,
                "scripts/normalize.py",
                "invalid.txt",
                "invalid-output.txt",
            ],
            cwd=directory,
        )
        if not (
            helper.returncode == 3
            and helper.stdout == ""
            and helper.stderr == "invalid UTF-8 input\n"
            and not (directory / "invalid-output.txt").exists()
        ):
            failures.append(
                "script-assisted-runtime helper: expected bounded invalid UTF-8 failure; "
                f"status={helper.returncode!r}, stdout={helper.stdout!r}, "
                f"stderr={helper.stderr!r}"
            )

    invalid_cases: list[tuple[str, Callable[[Path], None], str]] = []

    def unselect_runtime(directory: Path) -> None:
        path = directory / "RUNTIME.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "Selection status: SELECTED", "Selection status: UNSELECTED", 1
            ),
            encoding="utf-8",
        )

    def placeholder_runtime(directory: Path) -> None:
        path = directory / "RUNTIME.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "| Runtime | CPython |", "| Runtime | TBD |", 1
            ),
            encoding="utf-8",
        )

    invalid_cases.extend(
        [
            (
                "rejects an unselected retained runtime",
                unselect_runtime,
                "Selection status: SELECTED",
            ),
            (
                "rejects a runtime placeholder",
                placeholder_runtime,
                "unresolved scalar placeholder",
            ),
        ]
    )
    for name, mutation, diagnostic in invalid_cases:
        with tempfile.TemporaryDirectory(
            prefix="invalid-script-assisted-runtime-profile"
        ) as temporary:
            directory = Path(temporary)
            copy_fixture(directory)
            mutation(directory)
            validation = run_validator(directory)
            if validation.returncode == 0:
                failures.append(
                    f"script-assisted-runtime {name}: expected repository validation failure"
                )
            elif diagnostic not in validation.stderr:
                failures.append(
                    f"script-assisted-runtime {name}: expected actionable diagnostic "
                    f"containing {diagnostic!r}; diagnostics={validation.stderr!r}"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Script-assisted optional-runtime profile fixture tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
