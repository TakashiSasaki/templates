#!/usr/bin/env python3
"""Parity tests for concrete-profile and late-review Python validators."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_ROOT.parents[1]
TEMPLATE_SCRIPT_ROOT = REPOSITORY_ROOT / "template" / ".github" / "scripts"
VALIDATORS = {
    "concrete": (
        ["ruby", str(SCRIPT_ROOT / "validate-concrete-profile-consistency.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_concrete_profile_consistency.py"),
        ],
    ),
    "late-review": (
        ["ruby", str(SCRIPT_ROOT / "validate-late-review-contracts.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_late_review_contracts.py"),
        ],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    profile: str
    files: dict[str, str] = field(default_factory=dict)
    extra_skill: str = ""
    expected: dict[str, bool] = field(default_factory=dict)


def _skill(profile: str, extra: str = "") -> str:
    name = "agent-skill-template" if profile == "template-scaffold" else "example-skill"
    return f"""---
name: {name}
description: Example Skill
---
# Example Skill

Selected profiles: {profile}

{extra}"""


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="python-cutover-parity-") as directory:
        root = Path(directory)
        (root / "SKILL.md").write_text(
            _skill(case.profile, case.extra_skill), encoding="utf-8"
        )
        for relative, content in case.files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

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
            name="clean template scaffold",
            profile="template-scaffold",
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="template root implementation signal",
            profile="template-scaffold",
            files={"pyproject.toml": "[project]\nname = \"example\"\n"},
            expected={"concrete": True, "late-review": False},
        ),
        Case(
            name="instruction-only root implementation signal",
            profile="instruction-only",
            files={"main.py": "print('example')\n"},
            expected={"concrete": True, "late-review": False},
        ),
        Case(
            name="instruction-only source directory",
            profile="instruction-only",
            files={"src/main.py": "print('example')\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="browser directory without browser profile",
            profile="instruction-only",
            files={"web/app.js": "export const ready = true;\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="browser directory with browser profile",
            profile="browser-interface",
            files={"web/app.js": "export const ready = true;\n"},
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="asset declaration missing handling",
            profile="asset-driven",
            extra_skill=(
                "Asset: assets/example.txt\n"
                "Use when: deterministic example output is required\n"
            ),
            files={"assets/example.txt": "example\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="asset declaration complete",
            profile="asset-driven",
            extra_skill=(
                "Asset: assets/example.txt\n"
                "Use when: deterministic example output is required\n"
                "Handling: read-only input\n"
            ),
            files={"assets/example.txt": "example\n"},
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="incomplete headless service deployment",
            profile="headless-service",
            files={
                "RUNTIME.md": (
                    "# Runtime decision record\n\n"
                    "## Headless service deployment\n\n"
                    "| Item | Selected value |\n"
                    "|---|---|\n"
                    "| Supported | YES |\n"
                )
            },
            expected={"concrete": False, "late-review": True},
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
        "Concrete/late-review Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
