#!/usr/bin/env python3
"""Parity tests for the initial non-CLI Python validator ports."""

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


@dataclass(frozen=True)
class Case:
    name: str
    skill: str
    files: dict[str, str] = field(default_factory=dict)
    expected_success: bool = True


def _run(
    implementation: str,
    command: list[str],
    case: Case,
) -> str | None:
    with tempfile.TemporaryDirectory(prefix="initial-validator-parity-") as directory:
        root = Path(directory)
        (root / "SKILL.md").write_text(case.skill, encoding="utf-8")
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
        actual_success = completed.returncode == 0
        if actual_success == case.expected_success:
            return None
        return (
            f"{implementation} / {case.name}: expected success="
            f"{case.expected_success}, got {actual_success}; "
            f"stdout={completed.stdout.strip()!r}; "
            f"stderr={completed.stderr.strip()!r}"
        )


def _skill(profile: str, purpose: str = "Perform the documented operation.") -> str:
    return f"""---
name: example-skill
description: Example Skill
---
# Example Skill

## Purpose

{purpose}

## Use this skill when

Use this Skill for supplied example input.

## Workflow

Read the input and perform the documented steps.

## Output requirements

Return deterministic output.

## Validation

Check the output against the input.

## Safety and approval

Do not invent missing facts.

Selected profiles: {profile}
"""


VALID_ROUTING = """# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: installed human CLI command
Fallback 1: NONE
Fallback 2: NONE

## Contract index

The selected interface document is authoritative.

## Cross-interface invariants

All maintained routes preserve caller-visible semantics.

## Availability and failure behavior

Unavailable preferred interface behavior: report unavailability
Fallback activation conditions: documented conditions only
Failure classification exposed to callers: distinguish execution failures

## Decision rationale

Rationale: retain deterministic routing.
"""

VALID_CLI = """# Packaged CLI interface contract

## Human CLI

Command: skill-tool
Working directory: repository root

## Inputs, outputs, and side effects

| Item | Selected behavior |
|---|---|
| Standard output | JSON when requested |
"""

VALID_CLI_RUNTIME = """# Runtime decision record

## Status

Selection status: SELECTED

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | skill-tool |
"""

VALID_WEB = """# Optional human verification web interface

## Status and purpose

Supported: YES
Purpose: verification

## Human authorization and safety

Authentication: local session
Allowed users or network boundary: loopback users
Confirmation policy: required for mutations
"""

VALID_BROWSER_RUNTIME = """# Runtime decision record

## Status

Selection status: SELECTED

### Browser-interface commands

| Purpose | Exact command |
|---|---|
| Start human verification Web UI | bin/skill-web start |
| Stop human verification Web UI | bin/skill-web stop |
| Check human verification Web UI readiness | bin/skill-web ready |

## Optional human verification Web interface deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Web runtime or entry point | bin/skill-web |
| Enablement configuration | SKILL_WEB_UI=1 |
"""


def run() -> int:
    failures: list[str] = []

    placeholder_validators = {
        "Ruby placeholder": [
            "ruby",
            str(SCRIPT_ROOT / "validate-selected-contract-scalar-placeholders.rb"),
        ],
        "Python placeholder": [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_selected_contract_scalar_placeholders.py"),
        ],
    }
    placeholder_cases = [
        Case("concrete instruction-only", _skill("instruction-only")),
        Case(
            "instruction-only unresolved purpose",
            _skill("instruction-only", purpose="TBD"),
            expected_success=False,
        ),
        Case(
            "concrete CLI contracts",
            _skill("packaged-cli")
            + "\nCanonical command: skill-tool\n"
            + "Working directory: repository root\n"
            + "Preferred agent route: see INTERFACES.md\n"
            + "Detailed interface contract: CLI_INTERFACE.md\n",
            files={
                "INTERFACES.md": VALID_ROUTING,
                "CLI_INTERFACE.md": VALID_CLI,
                "RUNTIME.md": VALID_CLI_RUNTIME,
            },
        ),
        Case(
            "CLI runtime unresolved command",
            _skill("packaged-cli")
            + "\nCanonical command: skill-tool\n"
            + "Working directory: repository root\n"
            + "Preferred agent route: see INTERFACES.md\n"
            + "Detailed interface contract: CLI_INTERFACE.md\n",
            files={
                "INTERFACES.md": VALID_ROUTING,
                "CLI_INTERFACE.md": VALID_CLI,
                "RUNTIME.md": VALID_CLI_RUNTIME.replace(
                    "| Human CLI | skill-tool |", "| Human CLI | TBD |"
                ),
            },
            expected_success=False,
        ),
        Case(
            "concrete browser contracts",
            _skill("browser-interface")
            + "\nCanonical command: NOT APPLICABLE\n"
            + "Working directory: repository root\n",
            files={
                "WEB_INTERFACE.md": VALID_WEB,
                "RUNTIME.md": VALID_BROWSER_RUNTIME,
            },
        ),
        Case(
            "browser unresolved enablement",
            _skill("browser-interface")
            + "\nCanonical command: NOT APPLICABLE\n"
            + "Working directory: repository root\n",
            files={
                "WEB_INTERFACE.md": VALID_WEB,
                "RUNTIME.md": VALID_BROWSER_RUNTIME.replace(
                    "| Enablement configuration | SKILL_WEB_UI=1 |",
                    "| Enablement configuration | PLACEHOLDER |",
                ),
            },
            expected_success=False,
        ),
    ]

    for case in placeholder_cases:
        for implementation, command in placeholder_validators.items():
            failure = _run(implementation, command, case)
            if failure:
                failures.append(failure)

    review_validators = {
        "Ruby review follow-up": [
            "ruby",
            str(SCRIPT_ROOT / "validate-review-followup-contracts.rb"),
        ],
        "Python review follow-up": [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_review_followup_contracts.py"),
        ],
    }
    review_cases = [
        Case(
            "clean template scaffold",
            """---
name: template-skill
description: Template Skill
---
# Template Skill

Selected profiles: template-scaffold
""",
        ),
        Case(
            "template scaffold with root implementation",
            """---
name: template-skill
description: Template Skill
---
# Template Skill

Selected profiles: template-scaffold
""",
            files={"implementation.py": "print('unexpected')\n"},
            expected_success=False,
        ),
        Case("complete instruction-only", _skill("instruction-only")),
        Case(
            "concrete Skill with unresolved purpose",
            _skill("instruction-only", purpose="PLACEHOLDER"),
            expected_success=False,
        ),
        Case(
            "knowledge profile without operational reference",
            _skill("knowledge-augmented"),
            files={"references/README.md": "# References\n"},
            expected_success=False,
        ),
        Case(
            "knowledge profile with operational reference",
            _skill("knowledge-augmented")
            + "\nReference: references/guide.md\n"
            + "Read when: background is needed\n"
            + "Provides: authoritative guidance\n",
            files={
                "references/README.md": "# References\n",
                "references/guide.md": "# Guide\n",
            },
        ),
    ]

    for case in review_cases:
        for implementation, command in review_validators.items():
            failure = _run(implementation, command, case)
            if failure:
                failures.append(failure)

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        "Initial Ruby/Python validator parity tests passed "
        f"({len(placeholder_cases) + len(review_cases)} cases across two implementations)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
