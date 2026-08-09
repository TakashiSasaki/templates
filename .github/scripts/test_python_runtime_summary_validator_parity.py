#!/usr/bin/env python3
"""Parity tests for interface-runtime and interface-summary validators."""

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
    "runtime": (
        [
            "ruby",
            str(SCRIPT_ROOT / "validate-interface-runtime-consistency.rb"),
        ],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_interface_runtime_consistency.py"),
        ],
    ),
    "summary": (
        [
            "ruby",
            str(SCRIPT_ROOT / "validate-interface-summary-details.rb"),
        ],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_interface_summary_details.py"),
        ],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    source: str
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


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(
        prefix="python-runtime-summary-parity-"
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
            expected={"runtime": True, "summary": True},
        ),
        Case(
            name="valid packaged CLI fixture",
            source=".github/fixtures/profiles/packaged-cli",
            expected={"runtime": True, "summary": True},
        ),
        Case(
            name="valid MCP fixture",
            source=".github/fixtures/profiles/mcp-enabled",
            expected={"runtime": True, "summary": True},
        ),
        Case(
            name="packaged CLI missing runtime",
            source=".github/fixtures/profiles/packaged-cli",
            removes=("RUNTIME.md",),
            expected={"runtime": False, "summary": True},
        ),
        Case(
            name="packaged CLI command mismatch",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "CLI_INTERFACE.md": (
                    "Command: text-stat",
                    "Command: text-stat-alternate",
                )
            },
            expected={"runtime": False, "summary": True},
        ),
        Case(
            name="packaged CLI working-directory mismatch",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "SKILL.md": (
                    "Working directory: any directory with the installed command on PATH",
                    "Working directory: repository root",
                )
            },
            expected={"runtime": True, "summary": False},
        ),
        Case(
            name="MCP missing runtime",
            source=".github/fixtures/profiles/mcp-enabled",
            removes=("RUNTIME.md",),
            expected={"runtime": False, "summary": False},
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
            expected={"runtime": False, "summary": True},
        ),
        Case(
            name="MCP endpoint path mismatch",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "Endpoint URL: see RUNTIME.md",
                    "Endpoint URL: http://127.0.0.1:4570/wrong",
                )
            },
            expected={"runtime": True, "summary": False},
        ),
        Case(
            name="MCP invalid endpoint URI",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "Endpoint URL: see RUNTIME.md",
                    "Endpoint URL: http://[invalid",
                )
            },
            expected={"runtime": True, "summary": False},
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
        "Interface runtime/summary Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
