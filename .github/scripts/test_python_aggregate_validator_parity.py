#!/usr/bin/env python3
"""Parity tests for Python aggregate and repository validators."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_ROOT.parents[1]
VALIDATORS = {
    "profile": (
        ["ruby", str(SCRIPT_ROOT / "validate-profile-contracts.rb")],
        [sys.executable, str(SCRIPT_ROOT / "validate_profile_contracts.py")],
    ),
    "repository": (
        ["ruby", str(SCRIPT_ROOT / "validate-skill-repository.rb")],
        [sys.executable, str(SCRIPT_ROOT / "validate_skill_repository.py")],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    source: str
    git_metadata: bool = False
    writes: dict[str, str] = field(default_factory=dict)
    removes: tuple[str, ...] = ()
    replacements: dict[str, tuple[str, str]] = field(default_factory=dict)
    expected: dict[str, bool] = field(default_factory=dict)


def _materialize(case: Case, root: Path) -> None:
    source = REPOSITORY_ROOT / case.source
    shutil.copytree(source, root, dirs_exist_ok=True, symlinks=True)

    for relative in case.removes:
        path = root / relative
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()

    for relative, (before, after) in case.replacements.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if before not in text:
            raise RuntimeError(
                f"{case.name}: replacement source not found in {relative}: "
                f"{before!r}"
            )
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

    for relative, content in case.writes.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if case.git_metadata:
        subprocess.run(
            ["git", "init", "-q"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def _run(
    command: list[str],
    validator: str,
    case: Case,
) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(
        prefix="python-aggregate-parity-"
    ) as directory:
        root = Path(directory)
        _materialize(case, root)

        effective_command = (
            [*command, str(root)] if validator == "repository" else command
        )
        environment = os.environ.copy()
        environment.pop("RUBYOPT", None)
        environment.pop("GIT_DIR", None)
        environment.pop("GIT_WORK_TREE", None)
        environment.pop("GIT_INDEX_FILE", None)
        completed = subprocess.run(
            effective_command,
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr


def run() -> int:
    cases = [
        Case(
            name="template archive",
            source="template",
            expected={"profile": True, "repository": True},
        ),
        Case(
            name="packaged CLI worktree",
            source=".github/fixtures/profiles/packaged-cli",
            git_metadata=True,
            expected={"profile": True, "repository": True},
        ),
        Case(
            name="MCP archive",
            source=".github/fixtures/profiles/mcp-enabled",
            expected={"profile": True, "repository": True},
        ),
        Case(
            name="script-assisted archive",
            source=".github/fixtures/profiles/script-assisted",
            expected={"profile": True, "repository": True},
        ),
        Case(
            name="packaged CLI missing runtime",
            source=".github/fixtures/profiles/packaged-cli",
            removes=("RUNTIME.md",),
            expected={"profile": False, "repository": False},
        ),
        Case(
            name="undeclared script resource",
            source=".github/fixtures/profiles/script-assisted",
            writes={"scripts/extra.rb": "puts 'extra'\n"},
            expected={"profile": True, "repository": False},
        ),
        Case(
            name="concrete skill retains license template",
            source=".github/fixtures/profiles/packaged-cli",
            writes={"LICENSE.template": "Replace this license.\n"},
            expected={"profile": True, "repository": False},
        ),
        Case(
            name="invalid frontmatter name",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "SKILL.md": (
                    "name: deterministic-text-statistics-cli",
                    "name: Invalid_Name",
                )
            },
            expected={"profile": True, "repository": False},
        ),
    ]

    failures: list[str] = []
    for case in cases:
        for validator, (ruby_command, python_command) in VALIDATORS.items():
            ruby_result = _run(ruby_command, validator, case)
            python_result = _run(python_command, validator, case)
            expected_success = case.expected[validator]

            if ruby_result != python_result:
                failures.append(
                    f"{validator} / {case.name}: Ruby/Python output drift; "
                    f"ruby={ruby_result!r}; python={python_result!r}"
                )
                continue

            actual_success = ruby_result[0] == 0
            if actual_success != expected_success:
                failures.append(
                    f"{validator} / {case.name}: expected success="
                    f"{expected_success}, got {actual_success}; "
                    f"stdout={ruby_result[1].strip()!r}; "
                    f"stderr={ruby_result[2].strip()!r}"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        "Aggregate/repository Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
