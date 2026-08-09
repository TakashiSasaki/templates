#!/usr/bin/env python3
"""Parity tests for core and extended profile-contract validators."""

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
TEMPLATE_SCRIPT_ROOT = REPOSITORY_ROOT / "template" / ".github" / "scripts"
VALIDATORS = {
    "core": (
        ["ruby", str(SCRIPT_ROOT / "validate-core-profile-contracts.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_core_profile_contracts.py"),
        ],
    ),
    "extended": (
        ["ruby", str(SCRIPT_ROOT / "validate-extended-profile-contracts.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_extended_profile_contracts.py"),
        ],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    source: str
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


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(
        prefix="python-core-extended-parity-"
    ) as directory:
        root = Path(directory)
        _materialize(case, root)

        environment = os.environ.copy()
        environment.pop("RUBYOPT", None)
        completed = subprocess.run(
            command,
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
            name="template scaffold",
            source="template",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="template scaffold renamed",
            source="template",
            replacements={
                "SKILL.md": (
                    "name: agent-skill-template",
                    "name: renamed-template",
                )
            },
            expected={"core": False, "extended": False},
        ),
        Case(
            name="template runtime manifest",
            source="template",
            writes={"pyproject.toml": "[project]\nname = \"example\"\n"},
            expected={"core": True, "extended": False},
        ),
        Case(
            name="valid script-assisted fixture",
            source=".github/fixtures/profiles/script-assisted",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="valid packaged CLI fixture",
            source=".github/fixtures/profiles/packaged-cli",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="valid MCP fixture",
            source=".github/fixtures/profiles/mcp-enabled",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="valid browser fixture",
            source=".github/fixtures/profiles/browser-interface",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="valid headless fixture",
            source=".github/fixtures/profiles/headless-service",
            expected={"core": True, "extended": True},
        ),
        Case(
            name="packaged CLI missing runtime",
            source=".github/fixtures/profiles/packaged-cli",
            removes=("RUNTIME.md",),
            expected={"core": False, "extended": True},
        ),
        Case(
            name="duplicate packaged CLI profile",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "SKILL.md": (
                    "Selected profiles: packaged-cli",
                    "Selected profiles: packaged-cli, packaged-cli",
                )
            },
            expected={"core": False, "extended": True},
        ),
        Case(
            name="unknown packaged CLI profile",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "SKILL.md": (
                    "Selected profiles: packaged-cli",
                    "Selected profiles: packaged-cli, unknown-profile",
                )
            },
            expected={"core": False, "extended": True},
        ),
        Case(
            name="script declaration missing confirmation",
            source=".github/fixtures/profiles/script-assisted",
            replacements={
                "SKILL.md": (
                    "Human confirmation required: NO",
                    "Human confirmation required:",
                )
            },
            expected={"core": True, "extended": False},
        ),
        Case(
            name="MCP stdio support mismatch",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "## stdio MCP server variant\n\nSupported: YES",
                    "## stdio MCP server variant\n\nSupported: NO",
                )
            },
            expected={"core": True, "extended": False},
        ),
        Case(
            name="browser multiple interaction models",
            source=".github/fixtures/profiles/browser-interface",
            replacements={
                "WEB_INTERFACE.md": (
                    "- backend acts as an MCP client: NO",
                    "- backend acts as an MCP client: YES",
                )
            },
            expected={"core": True, "extended": False},
        ),
    ]

    failures: list[str] = []
    for case in cases:
        for validator, (ruby_command, python_command) in VALIDATORS.items():
            ruby_result = _run(ruby_command, case)
            python_result = _run(python_command, case)
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
        "Core/extended Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
