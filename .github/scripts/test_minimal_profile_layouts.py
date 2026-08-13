#!/usr/bin/env python3
"""Exercise reduced repository layouts for the non-application profiles."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = ROOT / ".github/fixtures/profiles"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"

EXPECTED_FILES = {
    "instruction-only": ["SKILL.md"],
    "knowledge-augmented": ["SKILL.md", "references/review-policy.md"],
    "asset-driven": ["SKILL.md", "assets/response-template.txt"],
    "script-assisted": ["SKILL.md", "scripts/normalize.py"],
    "combined-resources": [
        "SKILL.md",
        "assets/response-template.txt",
        "references/review-policy.md",
        "scripts/normalize.py",
    ],
}
INVALID_FIXTURE_FILES = {"unsupported-combination": ["SKILL.md"]}


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env.pop("GIT_INDEX_FILE", None)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def copy_fixture(name: str, directory: Path) -> None:
    shutil.copytree(
        FIXTURES_ROOT / name,
        directory,
        dirs_exist_ok=True,
        symlinks=True,
    )


def run_validator(directory: Path) -> subprocess.CompletedProcess[str]:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        completed = run(command, cwd=directory)
        if completed.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {completed.stderr}")
    return run([sys.executable, str(VALIDATOR), str(directory)], cwd=directory)


def fixture_inventory(name: str) -> list[str]:
    root = FIXTURES_ROOT / name
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if not path.is_dir()
    )


def replace_selected_profiles(directory: Path, replacement: str) -> None:
    path = directory / "SKILL.md"
    original = "Selected profiles: knowledge-augmented, asset-driven, script-assisted"
    content = path.read_text(encoding="utf-8")
    replaced = content.replace(
        original, f"Selected profiles: {replacement}", 1
    )
    if replaced == content:
        raise RuntimeError("combined fixture selected-profile line was not found")
    path.write_text(replaced, encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    combined_skill = (FIXTURES_ROOT / "combined-resources/SKILL.md").read_text(
        encoding="utf-8"
    )
    for required_text in (
        "The facts source, staging path, and output path must be distinct.",
        "Exact invocation: python scripts/normalize.py STAGING OUTPUT",
        "Save the completed UTF-8 response to the caller-supplied STAGING path",
        "the supplied facts source and staging file are unchanged by normalization",
    ):
        if required_text not in combined_skill:
            failures.append(
                "combined-resources: missing distinct staging-path contract: "
                f"{required_text!r}"
            )

    for name, expected in EXPECTED_FILES.items():
        actual = fixture_inventory(name)
        if actual != sorted(expected):
            failures.append(
                f"{name}: expected reduced layout {sorted(expected)!r}, got {actual!r}"
            )
            continue
        with tempfile.TemporaryDirectory(prefix=f"minimal-profile-{name}") as temporary:
            directory = Path(temporary)
            copy_fixture(name, directory)
            validation = run_validator(directory)
            if validation.returncode != 0:
                failures.append(
                    f"{name}: expected the complete reduced repository to pass; "
                    f"diagnostics={validation.stderr.strip()!r}"
                )

    for name, expected in INVALID_FIXTURE_FILES.items():
        actual = fixture_inventory(name)
        if actual != sorted(expected):
            failures.append(
                f"{name}: expected reduced invalid layout {sorted(expected)!r}, got {actual!r}"
            )
            continue
        with tempfile.TemporaryDirectory(prefix=f"invalid-profile-{name}") as temporary:
            directory = Path(temporary)
            copy_fixture(name, directory)
            validation = run_validator(directory)
            expected_diagnostic = (
                "'instruction-only' cannot be combined with resource, executable, "
                "or service profiles.\n"
            )
            if validation.returncode == 0:
                failures.append(
                    f"{name}: expected repository validation to reject the unsupported profile combination"
                )
            elif validation.stderr != expected_diagnostic:
                failures.append(
                    f"{name}: expected only the exclusive instruction-only diagnostic; "
                    f"diagnostics={validation.stderr!r}"
                )

    for fixture_name in ("script-assisted", "combined-resources"):
        with tempfile.TemporaryDirectory(prefix=f"{fixture_name}-execution") as temporary:
            directory = Path(temporary)
            copy_fixture(fixture_name, directory)
            input_name = (
                "response-staging.txt"
                if fixture_name == "combined-resources"
                else "input.txt"
            )
            input_path = directory / input_name
            input_path.write_bytes(b"alpha  \r\nbeta\t\r\n")
            input_before = input_path.read_bytes()

            facts_path: Path | None = None
            facts_before: bytes | None = None
            if fixture_name == "combined-resources":
                facts_path = directory / "facts.txt"
                facts_path.write_bytes(b"caller-supplied facts\n")
                facts_before = facts_path.read_bytes()

            helper = run(
                [
                    sys.executable,
                    "scripts/normalize.py",
                    input_name,
                    "output.txt",
                ],
                cwd=directory,
            )
            output_path = directory / "output.txt"
            output = output_path.read_bytes() if output_path.is_file() else None
            input_unchanged = input_path.read_bytes() == input_before
            facts_unchanged = (
                facts_path is None or facts_path.read_bytes() == facts_before
            )
            if not (
                helper.returncode == 0
                and helper.stderr == ""
                and helper.stdout == "output.txt\n"
                and output == b"alpha\nbeta\n"
                and input_unchanged
                and facts_unchanged
            ):
                failures.append(
                    f"{fixture_name} helper: expected deterministic normalization without modifying source inputs; "
                    f"status={helper.returncode!r}, stdout={helper.stdout!r}, "
                    f"stderr={helper.stderr!r}, output={output!r}, "
                    f"input_unchanged={input_unchanged!r}, facts_unchanged={facts_unchanged!r}"
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
                    f"{fixture_name} helper: expected bounded invalid UTF-8 failure; "
                    f"status={helper.returncode!r}, stdout={helper.stdout!r}, "
                    f"stderr={helper.stderr!r}"
                )

    invalid_cases: list[tuple[str, str, Callable[[Path], None]]] = []

    invalid_cases.append(
        (
            "instruction-only rejects a retained runtime contract",
            "instruction-only",
            lambda directory: (directory / "RUNTIME.md").write_text(
                "# Unsupported runtime contract\n", encoding="utf-8"
            ),
        )
    )
    invalid_cases.append(
        (
            "knowledge-augmented rejects a missing declared reference",
            "knowledge-augmented",
            lambda directory: (directory / "references/review-policy.md").unlink(),
        )
    )
    invalid_cases.append(
        (
            "asset-driven rejects an undeclared retained asset",
            "asset-driven",
            lambda directory: (directory / "assets/undeclared.txt").write_text(
                "undeclared\n", encoding="utf-8"
            ),
        )
    )
    invalid_cases.append(
        (
            "script-assisted rejects an undeclared retained helper",
            "script-assisted",
            lambda directory: (directory / "scripts/undeclared.py").write_text(
                "print('undeclared')\n", encoding="utf-8"
            ),
        )
    )
    invalid_cases.extend(
        [
            (
                "combined resources require knowledge-augmented",
                "combined-resources",
                lambda directory: replace_selected_profiles(
                    directory, "asset-driven, script-assisted"
                ),
            ),
            (
                "combined resources require asset-driven",
                "combined-resources",
                lambda directory: replace_selected_profiles(
                    directory, "knowledge-augmented, script-assisted"
                ),
            ),
            (
                "combined resources require script-assisted",
                "combined-resources",
                lambda directory: replace_selected_profiles(
                    directory, "knowledge-augmented, asset-driven"
                ),
            ),
        ]
    )

    for name, fixture, mutation in invalid_cases:
        with tempfile.TemporaryDirectory(prefix="invalid-minimal-profile") as temporary:
            directory = Path(temporary)
            copy_fixture(fixture, directory)
            mutation(directory)
            validation = run_validator(directory)
            if validation.returncode == 0:
                failures.append(f"{name}: expected validation failure")
            elif not validation.stderr.strip():
                failures.append(f"{name}: expected an actionable diagnostic")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Minimal profile repository layout tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
