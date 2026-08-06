#!/usr/bin/env python3
"""Run packaged-CLI contract cases against both Ruby and Python validators."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
VALIDATORS = {
    "Ruby exit-code": ["ruby", str(SCRIPT_ROOT / "validate-cli-exit-code-contract.rb")],
    "Python exit-code": [
        sys.executable,
        str(SCRIPT_ROOT / "validate_cli_exit_code_contract.py"),
    ],
    "Ruby structured-output": [
        "ruby",
        str(SCRIPT_ROOT / "validate-cli-structured-output-contract.rb"),
    ],
    "Python structured-output": [
        sys.executable,
        str(SCRIPT_ROOT / "validate_cli_structured_output_contract.py"),
    ],
}


def _run_validator(
    name: str,
    command: list[str],
    root: Path,
    expected_success: bool,
) -> str | None:
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
    if actual_success == expected_success:
        return None
    return (
        f"{name}: expected success={expected_success}, got {actual_success}; "
        f"stdout={completed.stdout.strip()!r}; stderr={completed.stderr.strip()!r}"
    )


def _write_skill(root: Path) -> None:
    (root / "SKILL.md").write_text(
        "Selected profiles: packaged-cli\n", encoding="utf-8"
    )


def _exit_contract(zero_meaning: str, nonzero_meaning: str) -> str:
    return f"""# Packaged CLI interface contract

## Human CLI

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | {zero_meaning} |
| 1 | {nonzero_meaning} |
"""


def _structured_contract(
    mode_selector: str | None,
    format_name: str,
    version_field: str,
) -> str:
    selector = "" if mode_selector is None else mode_selector
    return f"""# Packaged CLI interface contract

## Human CLI

Command: skill-tool
Working directory: repository root

### Structured output

Mode selector: {selector}
Format: {format_name}
Contract version field: {version_field}
"""


def run() -> int:
    failures: list[str] = []

    exit_cases = [
        ("explicit successful zero", "Successful execution", "Negative domain result", True),
        ("completed successfully", "Command completed successfully", "Invalid invocation", True),
        ("completed normally", "Completed normally", "Invalid invocation", True),
        ("clean termination", "Clean termination", "Invalid invocation", True),
        ("OK", "OK", "Invalid invocation", True),
        ("negative zero outcome", "Negative domain result", "Invalid invocation", False),
        ("failure zero outcome", "Execution failure", "Invalid invocation", False),
        ("negated success", "Not successful", "Invalid invocation", False),
        ("unsuccessful", "Unsuccessful execution", "Invalid invocation", False),
        ("timeout", "Operation timed out", "Invalid invocation", False),
        ("cancellation", "Cancelled by user", "Invalid invocation", False),
        ("aborted", "Operation aborted", "Invalid invocation", False),
        ("NONE meaning", "Successful execution", "NONE", False),
        ("NOT APPLICABLE meaning", "Successful execution", "NOT APPLICABLE", False),
        ("NOT SUPPORTED meaning", "Successful execution", "NOT SUPPORTED", False),
        ("TBD meaning", "Successful execution", "TBD", False),
    ]

    for case_name, zero_meaning, nonzero_meaning, expected_success in exit_cases:
        with tempfile.TemporaryDirectory(prefix="python-cli-exit-parity-") as directory:
            root = Path(directory)
            _write_skill(root)
            (root / "CLI_INTERFACE.md").write_text(
                _exit_contract(zero_meaning, nonzero_meaning), encoding="utf-8"
            )
            for implementation in ("Ruby exit-code", "Python exit-code"):
                failure = _run_validator(
                    f"{implementation} / {case_name}",
                    VALIDATORS[implementation],
                    root,
                    expected_success,
                )
                if failure:
                    failures.append(failure)

    exit_shape_cases = [
        (
            "duplicate code with escaped pipe",
            """# Packaged CLI interface contract

## Human CLI

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution |
| 1 | Validation failure |
| 1 | Validation \\| runtime failure |
""",
        ),
        (
            "unexpected third table cell",
            """# Packaged CLI interface contract

## Human CLI

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution |
| 1 | Invalid invocation |
| bogus | Invalid | extra |
""",
        ),
    ]
    for case_name, contract in exit_shape_cases:
        with tempfile.TemporaryDirectory(
            prefix="python-cli-exit-shape-parity-"
        ) as directory:
            root = Path(directory)
            _write_skill(root)
            (root / "CLI_INTERFACE.md").write_text(contract, encoding="utf-8")
            for implementation in ("Ruby exit-code", "Python exit-code"):
                failure = _run_validator(
                    f"{implementation} / {case_name}",
                    VALIDATORS[implementation],
                    root,
                    False,
                )
                if failure:
                    failures.append(failure)

    structured_cases = [
        ("long option with value", "--output json", "JSON", "contractVersion", True),
        ("boolean JSON flag", "--json", "NDJSON", "metadata.contractVersion", True),
        (
            "environment assignment",
            "SKILL_OUTPUT=json",
            "JSON",
            "/metadata/contractVersion",
            True,
        ),
        (
            "named environment assignment",
            "environment variable: SKILL_OUTPUT=json",
            "JSON",
            "contractVersion",
            True,
        ),
        (
            "named subcommand",
            "subcommand: export-json",
            "TOML",
            "contractVersion",
            True,
        ),
        (
            "Apache Avro",
            "--format avro",
            "Apache Avro",
            "metadata.contractVersion",
            True,
        ),
        (
            "vendor media type",
            "--media-type application/vnd.example+json",
            "application/vnd.example+json",
            "contractVersion",
            True,
        ),
        ("missing selector", None, "JSON", "contractVersion", False),
        ("TODO selector", "TODO", "JSON", "contractVersion", False),
        ("automatic selector", "automatic", "JSON", "contractVersion", False),
        (
            "prose selector",
            "use the structured mode documented elsewhere",
            "JSON",
            "contractVersion",
            False,
        ),
        (
            "environment name without value",
            "environment variable: SKILL_OUTPUT",
            "JSON",
            "contractVersion",
            False,
        ),
        ("TBD named option", "option: TBD", "JSON", "contractVersion", False),
        (
            "pending subcommand",
            "subcommand: pending",
            "JSON",
            "contractVersion",
            False,
        ),
        (
            "TBD option argument",
            "--output TBD",
            "JSON",
            "contractVersion",
            False,
        ),
        (
            "DEFAULT environment value",
            "SKILL_OUTPUT=DEFAULT",
            "JSON",
            "contractVersion",
            False,
        ),
        (
            "tabbed NOT SUPPORTED selector",
            "option: NOT\tSUPPORTED",
            "JSON",
            "contractVersion",
            False,
        ),
        (
            "spaced SEE DOCUMENTATION selector",
            "option: SEE   DOCUMENTATION",
            "JSON",
            "contractVersion",
            False,
        ),
        ("plain text", "--output text", "plain text only", "contractVersion", False),
        (
            "tabbed plain text",
            "--output text",
            "plain\ttext",
            "contractVersion",
            False,
        ),
        ("human readable", "--human", "human readable", "contractVersion", False),
        (
            "unstructured",
            "--output raw",
            "unstructured output",
            "contractVersion",
            False,
        ),
        (
            "generic custom",
            "--output custom",
            "custom",
            "contractVersion",
            False,
        ),
        (
            "tabbed NOT APPLICABLE format",
            "--json",
            "NOT\tAPPLICABLE",
            "contractVersion",
            False,
        ),
        (
            "missing version field",
            "--json",
            "JSON",
            "no version field",
            False,
        ),
        (
            "spaced missing version field",
            "--json",
            "JSON",
            "NO\tVERSION  FIELD",
            False,
        ),
        (
            "prose version field",
            "--json",
            "JSON",
            "the version field in metadata",
            False,
        ),
    ]

    for case_name, selector, format_name, version_field, expected_success in structured_cases:
        with tempfile.TemporaryDirectory(
            prefix="python-cli-structured-parity-"
        ) as directory:
            root = Path(directory)
            _write_skill(root)
            (root / "CLI_INTERFACE.md").write_text(
                _structured_contract(selector, format_name, version_field),
                encoding="utf-8",
            )
            for implementation in (
                "Ruby structured-output",
                "Python structured-output",
            ):
                failure = _run_validator(
                    f"{implementation} / {case_name}",
                    VALIDATORS[implementation],
                    root,
                    expected_success,
                )
                if failure:
                    failures.append(failure)

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        "Ruby/Python CLI contract parity tests passed "
        f"({len(exit_cases) + len(exit_shape_cases) + len(structured_cases)} cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
