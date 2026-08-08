#!/usr/bin/env python3
"""Audit the canonical template-owned Python validator boundary."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCRIPTS = REPOSITORY_ROOT / ".github" / "scripts"
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

DIRECT_CANONICAL_PATTERN = re.compile(
    r"python(?:\s+-\S+)*\s+"
    r"template/\.github/scripts/validate_skill_repository\.py"
    r"\s+template(?:\s|$)"
)
DIRECT_LEGACY_PATTERN = re.compile(
    r"python(?:\s+-\S+)*\s+"
    r"\.github/scripts/validate_skill_repository\.py"
    r"\s+template(?:\s|$)"
)
WORKDIR_PATTERN = re.compile(
    r"python(?:\s+-\S+)*\s+"
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


def _load_workflow(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"workflow is not a mapping: {path}")
    return value


def _steps(workflow: dict[str, object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return result
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if isinstance(steps, list):
            result.extend(step for step in steps if isinstance(step, dict))
    return result


def _has_direct_canonical_invocation(workflow: dict[str, object]) -> bool:
    return any(
        isinstance(step.get("run"), str)
        and DIRECT_CANONICAL_PATTERN.search(str(step["run"])) is not None
        for step in _steps(workflow)
    )


def _has_legacy_direct_invocation(workflow: dict[str, object]) -> bool:
    return any(
        step.get("working-directory") != "template"
        and isinstance(step.get("run"), str)
        and DIRECT_LEGACY_PATTERN.search(str(step["run"])) is not None
        for step in _steps(workflow)
    )


def _has_template_workdir_invocation(workflow: dict[str, object]) -> bool:
    return any(
        step.get("working-directory") == "template"
        and isinstance(step.get("run"), str)
        and WORKDIR_PATTERN.search(str(step["run"])) is not None
        for step in _steps(workflow)
    )


def _test_workflow_matchers(failures: list[str]) -> None:
    direct = {
        "jobs": {
            "test": {
                "steps": [
                    {
                        "run": "python -I template/.github/scripts/validate_skill_repository.py template"
                    }
                ]
            }
        }
    }
    if not _has_direct_canonical_invocation(direct):
        failures.append("workflow matcher rejected canonical invocation with Python flags")

    legacy = {
        "jobs": {
            "test": {
                "steps": [
                    {"run": "python .github/scripts/validate_skill_repository.py template"}
                ]
            }
        }
    }
    if not _has_legacy_direct_invocation(legacy):
        failures.append("workflow matcher did not detect legacy root invocation")

    workdir = {
        "jobs": {
            "test": {
                "steps": [
                    {
                        "run": "python .github/scripts/validate_skill_repository.py",
                        "shell": "bash",
                        "working-directory": "template",
                    }
                ]
            }
        }
    }
    if not _has_template_workdir_invocation(workdir):
        failures.append("workflow matcher depends on YAML key order for template working-directory")


def run() -> int:
    failures: list[str] = []
    _test_workflow_matchers(failures)

    ruby_files = sorted(
        path.relative_to(TEMPLATE_SCRIPTS).as_posix()
        for path in TEMPLATE_SCRIPTS.rglob("*.rb")
    )
    if ruby_files:
        failures.append(
            "copyable template retained Ruby validation files: " + ", ".join(ruby_files)
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

    legacy_root_files = sorted(
        relative
        for relative in REQUIRED_TEMPLATE_FILES - {"test_template_baseline.py"}
        if (SOURCE_SCRIPTS / relative).exists()
    )
    if legacy_root_files:
        failures.append(
            "source root retained alternate copies of template-owned Python validators: "
            + ", ".join(legacy_root_files)
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        failures.append("distribution manifest schema_version is not 2")
    for legacy_key in ("mirrors", "distribution_owned_files"):
        if legacy_key in manifest:
            failures.append(f"distribution manifest retained legacy field: {legacy_key}")
    distribution_files = set(manifest.get("distribution_files", []))
    missing_from_inventory = sorted(
        f".github/scripts/{relative}"
        for relative in REQUIRED_TEMPLATE_FILES
        if f".github/scripts/{relative}" not in distribution_files
    )
    if missing_from_inventory:
        failures.append(
            "canonical distribution inventory omits Python validator files: "
            + ", ".join(missing_from_inventory)
        )

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
        source_workflow = _load_workflow(source_workflow_path)
        if _has_legacy_direct_invocation(source_workflow):
            failures.append(
                "source workflow still executes a root Python validator: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )
        if not _has_direct_canonical_invocation(source_workflow):
            failures.append(
                "source workflow does not execute the template-owned Python validator: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )

    for source_workflow_path in TEMPLATE_WORKDIR_SOURCE_WORKFLOW_PATHS:
        source_workflow = _load_workflow(source_workflow_path)
        if not _has_template_workdir_invocation(source_workflow):
            failures.append(
                "source workflow does not execute the Python repository validator "
                "from working-directory template: "
                f"{source_workflow_path.relative_to(REPOSITORY_ROOT)}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Canonical template-owned Python validator boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
