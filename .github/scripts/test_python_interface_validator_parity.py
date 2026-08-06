#!/usr/bin/env python3
"""Parity tests for interface-routing and decomposed-interface validators."""

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
    "routing": (
        ["ruby", str(SCRIPT_ROOT / "validate-interface-routing-contract.rb")],
        [
            sys.executable,
            str(SCRIPT_ROOT / "validate_interface_routing_contract.py"),
        ],
    ),
    "decomposed": (
        ["ruby", str(SCRIPT_ROOT / "validate-decomposed-interface-contracts.rb")],
        [
            sys.executable,
            str(SCRIPT_ROOT / "validate_decomposed_interface_contracts.py"),
        ],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    source: str | None = None
    writes: dict[str, str] = field(default_factory=dict)
    removes: tuple[str, ...] = ()
    replacements: dict[str, tuple[str, str]] = field(default_factory=dict)
    expected: dict[str, bool] = field(default_factory=dict)


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
                f"{case.name}: replacement source not found in {relative}: {before!r}"
            )
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

    for relative, content in case.writes.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="python-interface-parity-") as directory:
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
    minimal_instruction_skill = """---
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
            expected={"routing": True, "decomposed": True},
        ),
        Case(
            name="valid packaged CLI fixture",
            source=".github/fixtures/profiles/packaged-cli",
            expected={"routing": True, "decomposed": True},
        ),
        Case(
            name="valid MCP fixture",
            source=".github/fixtures/profiles/mcp-enabled",
            expected={"routing": True, "decomposed": True},
        ),
        Case(
            name="packaged CLI missing routing contract",
            source=".github/fixtures/profiles/packaged-cli",
            removes=("INTERFACES.md",),
            expected={"routing": False, "decomposed": True},
        ),
        Case(
            name="packaged CLI missing CLI contract",
            source=".github/fixtures/profiles/packaged-cli",
            removes=("CLI_INTERFACE.md",),
            expected={"routing": False, "decomposed": False},
        ),
        Case(
            name="instruction-only retained routing contract",
            source=None,
            writes={
                "SKILL.md": minimal_instruction_skill,
                "INTERFACES.md": "# Retained routing contract\n",
            },
            expected={"routing": False, "decomposed": True},
        ),
        Case(
            name="instruction-only retained CLI contract",
            source=None,
            writes={
                "SKILL.md": minimal_instruction_skill,
                "CLI_INTERFACE.md": "# Retained CLI contract\n",
            },
            expected={"routing": True, "decomposed": False},
        ),
        Case(
            name="duplicate packaged CLI route",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "INTERFACES.md": (
                    "Fallback 1: stable in-place CLI launcher",
                    "Fallback 1: installed human CLI command",
                )
            },
            expected={"routing": False, "decomposed": True},
        ),
        Case(
            name="packaged CLI unresolved status",
            source=".github/fixtures/profiles/packaged-cli",
            replacements={
                "CLI_INTERFACE.md": (
                    "Selection status: SELECTED",
                    "Selection status: TODO",
                )
            },
            expected={"routing": True, "decomposed": False},
        ),
        Case(
            name="MCP missing interface contract",
            source=".github/fixtures/profiles/mcp-enabled",
            removes=("MCP_INTERFACE.md",),
            expected={"routing": False, "decomposed": False},
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
        "Interface routing/decomposition Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
