#!/usr/bin/env python3
"""Check completion hygiene for a minimal concrete Skill."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

SOURCE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = SOURCE_ROOT / ".github/fixtures/profiles/instruction-only"
VALIDATOR = SOURCE_ROOT / "template/.github/scripts/validate_skill_repository.py"
CANONICAL_LICENSE_PATH = SOURCE_ROOT / "template/LICENSE"
LICENSE_TEMPLATE_PATH = SOURCE_ROOT / "template/LICENSE.template"
FAILURES: list[str] = []

EXPECTED_CANONICAL_LICENSE = """MIT No Attribution

Copyright 2026 Takashi Sasaki

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
CANONICAL_TEMPLATE_README = """# Language-neutral Agent Skill Template

This repository is a template for developing a portable Agent Skill. Its root is intended to become the installable Skill directory directly:
"""
CONCRETE_README = """# Evidence summary skill

This repository contains the completed evidence-summary Agent Skill.
"""


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    return env


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=clean_env(),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def run_or_raise(command: list[str], *, cwd: Path) -> None:
    result = run(command, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {command!r}; status={result.returncode!r}; "
            f"stdout={result.stdout!r}; stderr={result.stderr!r}"
        )


def validate(directory: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, str(VALIDATOR), str(directory)],
        cwd=SOURCE_ROOT,
    )


def materialize(action: Callable[[Path], None]) -> None:
    with tempfile.TemporaryDirectory(prefix="concrete-skill-completion") as temporary:
        directory = Path(temporary)
        shutil.copytree(FIXTURE, directory, dirs_exist_ok=True, symlinks=True)
        run_or_raise(["git", "init", "--quiet"], cwd=directory)
        run_or_raise(["git", "add", "."], cwd=directory)
        action(directory)


def expect_success(label: str, mutation: Callable[[Path], None] | None = None) -> None:
    def action(directory: Path) -> None:
        if mutation:
            mutation(directory)
        result = validate(directory)
        if not (
            result.returncode == 0
            and result.stderr == ""
            and "Agent Skill repository structure and profile contracts are valid."
            in result.stdout
        ):
            FAILURES.append(
                f"{label}: expected success; status={result.returncode!r}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )

    materialize(action)


def expect_failure(
    label: str, diagnostic: str, mutation: Callable[[Path], None]
) -> None:
    def action(directory: Path) -> None:
        mutation(directory)
        run_or_raise(["git", "add", "-A"], cwd=directory)
        result = validate(directory)
        if result.returncode == 0:
            FAILURES.append(
                f"{label}: expected validation failure; stdout={result.stdout!r}"
            )
        elif result.stderr != f"{diagnostic}\n":
            FAILURES.append(
                f"{label}: expected only {diagnostic!r}; stderr={result.stderr!r}"
            )

    materialize(action)


def main() -> int:
    if not (
        CANONICAL_LICENSE_PATH.is_file()
        and not CANONICAL_LICENSE_PATH.is_symlink()
        and CANONICAL_LICENSE_PATH.read_text(encoding="utf-8")
        == EXPECTED_CANONICAL_LICENSE
    ):
        FAILURES.append(
            "canonical template license: expected the exact maintained MIT-0 text"
        )

    license_guidance = (
        LICENSE_TEMPLATE_PATH.read_text(encoding="utf-8")
        if LICENSE_TEMPLATE_PATH.is_file() and not LICENSE_TEMPLATE_PATH.is_symlink()
        else ""
    )
    for required_text in (
        "keep LICENSE to use MIT-0 for the concrete skill",
        "replace LICENSE with another license appropriate for the concrete skill",
        "remove LICENSE.template",
    ):
        if required_text not in license_guidance:
            FAILURES.append(
                f"license template guidance: missing {required_text!r}"
            )

    expect_success("completed instruction-only skill")
    expect_success(
        "concrete README is allowed",
        lambda directory: (directory / "README.md").write_text(
            CONCRETE_README, encoding="utf-8"
        ),
    )
    expect_success(
        "concrete skill may retain canonical MIT-0 license",
        lambda directory: shutil.copy2(
            CANONICAL_LICENSE_PATH, directory / "LICENSE"
        ),
    )
    expect_failure(
        "license placeholder residue",
        "A concrete skill must replace or remove LICENSE.template.",
        lambda directory: (directory / "LICENSE.template").write_text(
            "Select a license appropriate for the concrete skill.\n",
            encoding="utf-8",
        ),
    )
    expect_failure(
        "canonical README identity residue",
        "A concrete skill must replace or remove the canonical template README identity.",
        lambda directory: (directory / "README.md").write_text(
            CANONICAL_TEMPLATE_README, encoding="utf-8"
        ),
    )

    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        return 1
    print("Concrete skill completion hygiene tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
