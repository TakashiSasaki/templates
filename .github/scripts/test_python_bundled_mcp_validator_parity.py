#!/usr/bin/env python3
"""Parity tests for the bundled MCP client consistency validator."""

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
RUBY_COMMAND = [
    "ruby",
    str(SCRIPT_ROOT / "validate-bundled-mcp-client-consistency.rb"),
]
PYTHON_COMMAND = [
    sys.executable,
    str(TEMPLATE_SCRIPT_ROOT / "validate_bundled_mcp_client_consistency.py"),
]


@dataclass(frozen=True)
class Case:
    name: str
    source: str | None = None
    writes: dict[str, str] = field(default_factory=dict)
    removes: tuple[str, ...] = ()
    replacements: dict[str, tuple[str, str]] = field(default_factory=dict)
    expected_success: bool = True


def _materialize(case: Case, root: Path) -> None:
    if case.source is not None:
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


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(
        prefix="python-bundled-mcp-parity-"
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
    instruction_skill = """---
name: example-skill
description: Example Skill
---
# Example Skill

Selected profiles: instruction-only
"""
    cases = [
        Case(
            name="template scaffold",
            source="template",
            expected_success=True,
        ),
        Case(
            name="inactive instruction-only profile",
            writes={"SKILL.md": instruction_skill},
            expected_success=True,
        ),
        Case(
            name="valid MCP fixture",
            source=".github/fixtures/profiles/mcp-enabled",
            expected_success=True,
        ),
        Case(
            name="missing MCP interface",
            source=".github/fixtures/profiles/mcp-enabled",
            removes=("MCP_INTERFACE.md",),
            expected_success=False,
        ),
        Case(
            name="missing runtime",
            source=".github/fixtures/profiles/mcp-enabled",
            removes=("RUNTIME.md",),
            expected_success=False,
        ),
        Case(
            name="public support mismatch",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "## Bundled ad hoc MCP tool client\n\nSupported: YES",
                    "## Bundled ad hoc MCP tool client\n\nSupported: NO",
                )
            },
            expected_success=False,
        ),
        Case(
            name="transport mismatch",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "Transport used: both",
                    "Transport used: stdio",
                )
            },
            expected_success=False,
        ),
        Case(
            name="required stdio variant disabled",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "## stdio MCP server variant\n\nSupported: YES",
                    "## stdio MCP server variant\n\nSupported: NO",
                )
            },
            expected_success=False,
        ),
        Case(
            name="task support mismatch",
            source=".github/fixtures/profiles/mcp-enabled",
            replacements={
                "MCP_INTERFACE.md": (
                    "Task or extension support: NOT SUPPORTED",
                    "Task or extension support: bounded tasks",
                )
            },
            expected_success=False,
        ),
    ]

    failures: list[str] = []
    for case in cases:
        ruby_result = _run(RUBY_COMMAND, case)
        python_result = _run(PYTHON_COMMAND, case)

        if ruby_result != python_result:
            failures.append(
                f"{case.name}: Ruby/Python output drift; "
                f"ruby={ruby_result!r}; python={python_result!r}"
            )
            continue

        actual_success = ruby_result[0] == 0
        if actual_success != case.expected_success:
            failures.append(
                f"{case.name}: expected success={case.expected_success}, "
                f"got {actual_success}; stdout={ruby_result[1].strip()!r}; "
                f"stderr={ruby_result[2].strip()!r}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        "Bundled MCP client Ruby-Python parity tests passed "
        f"({len(cases)} cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
