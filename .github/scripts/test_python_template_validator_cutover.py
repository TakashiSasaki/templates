#!/usr/bin/env python3
"""Audit the copyable template's Python-only validator cutover."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SCRIPTS = REPOSITORY_ROOT / "template" / ".github" / "scripts"
MANIFEST_PATH = REPOSITORY_ROOT / "distribution-manifest.json"
WORKFLOW_PATH = (
    REPOSITORY_ROOT / "template" / ".github" / "workflows" / "validate-skill.yml"
)
DIRECT_SOURCE_WORKFLOW_PATHS = (
    REPOSITORY_ROOT / ".github" / "workflows" / "validate-portable-consumption.yml",
    REPOSITORY_ROOT / ".github" / "workflows" / "validate-structure.yml",
)
TEMPLATE_WORKDIR_SOURCE_WORKFLOW_PATHS = (
    REPOSITORY_ROOT / ".github" / "workflows" / "validate-extended-profile-contracts.yml",
)

CANONICAL_DIRECT_PATTERN = re.compile(
    r"python(?:\s+-\S+)*\s+"
    r"template/\.github/scripts/validate_skill_repository\.py"
    r"\s+template(?:\s|$)"
)
LEGACY_DIRECT_PATTERN = re.compile(
    r"python(?:\s+-\S+)*\s+"
    r"\.github/scripts/validate_skill_repository\.py"
    r"\s+template(?:\s|$)"
)
TEMPLATE_WORKDIR_PATTERN = re.compile(
    r"working-directory:\s*template\s*\n"
    r"\s*run:\s*python(?:\s+-\S+)*\s+"
    r"\.github/scripts/validate_skill_repository\.py(?:\s|$)"
)

REQUIRED_TEMPLATE_FILES = {
    "test_template_baseline.py",
    "lib/core_profile_interfaces.py",
    "lib/core_profile_runtime.py",
    "lib/profile_contracts.py",
    "validate_bundled_mcp_client_consistency.py",
    "validate_cli_exit_code_contract.py",
    "validate_cli_structured_output_contract.py",
    "validate_concrete_profile_consistency.py",
    "validate_core_profile_contracts.py",
    "validate_decomposed_interface_contracts.py",
    "validate_extended_profile_contracts.py",
    "validate_interface_routing_contract.py",
    "validate_interface_runtime_consistency.py",
    "validate_interface_summary_details.py",
    "validate_late_review_contracts.py",
    "validate_mcp_runtime_authority.py",
    "validate_profile_contracts.py",
    "validate_review_followup_contracts.py",
    "validate_selected_contract_scalar_placeholders.py",
    "validate_skill_repository.py",
}


def run() -> int:
    failures: list[str] = []

    ruby_files = sorted(
        path.relative_to(TEMPLATE_SCRIPTS).as_posix()
        for path in TEMPLATE_SCRIPTS.rglob("*.rb")
    )
    if ruby_files:
        failures.append(
            "copyable template retained Ruby validation files: "
            + ", ".join(ruby_files)
        )

    actual_files = {
        path.relative_to(TEMPLATE_SCRIPTS).as_posix()
        for path in TEMPLATE_SCRIPTS.rglob("*")
        if path.is_file()
    }
    missing_files = sorted(REQUIRED_TEMPLATE_FILES - actual_files)
    if missing_files:
        failures.append(
            "copyable template is missing Python validation files: "
            + ", ".join(missing_files)
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ruby_mirrors = [
        mirror
        for mirror in manifest.get("mirrors", [])
        if str(mirror.get("source", "")).endswith(".rb")
        or str(mirror.get("destination", "")).endswith(".rb")
    ]
    if ruby_mirrors:
        failures.append("distribution manifest retained Ruby validator projections")

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for forbidden in ("ruby/setup-ruby", "ruby .github/scripts/"):
        if forbidden in workflow:
            failures.append(
                f"copyable validation workflow retained Ruby execution: {forbidden}"
            )
    for required in (
        "actions/setup-python@v6",
        'python-version: "3.12"',
        "PyYAML==6.0.3",
        "python .github/scripts/validate_skill_repository.py",
        "python .github/scripts/test_template_baseline.py",
    ):
        if required not in workflow:
            failures.append(
                f"copyable validation workflow is missing required Python setup: {required}"
            )

    for source_workflow_path in DIRECT_SOURCE_WORKFLOW_PATHS:
        source_workflow = source_workflow_path.read_text(encoding="utf-8")
        if LEGACY_DIRECT_PATTERN.search(source_workflow):
            failures.append(
                "source workflow still executes the root projected Python validator: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )
        if not CANONICAL_DIRECT_PATTERN.search(source_workflow):
            failures.append(
                "source workflow does not execute the template-owned Python validator: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )

    for source_workflow_path in TEMPLATE_WORKDIR_SOURCE_WORKFLOW_PATHS:
        source_workflow = source_workflow_path.read_text(encoding="utf-8")
        if not TEMPLATE_WORKDIR_PATTERN.search(source_workflow):
            failures.append(
                "source workflow does not execute the Python repository validator "
                "from working-directory template: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Python-only template validator cutover checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
