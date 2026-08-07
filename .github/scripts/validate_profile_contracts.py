#!/usr/bin/env python3
"""Run all requested Agent Skill profile validators."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


DIRECT_VALIDATORS = (
    "validate_interface_routing_contract.py",
    "validate_decomposed_interface_contracts.py",
    "validate_selected_contract_scalar_placeholders.py",
    "validate_cli_structured_output_contract.py",
    "validate_cli_exit_code_contract.py",
    "validate_mcp_runtime_authority.py",
    "validate_interface_runtime_consistency.py",
    "validate_bundled_mcp_client_consistency.py",
    "validate_interface_summary_details.py",
)

DEFAULT_RULE_VALIDATORS = (
    "validate_core_profile_contracts.py",
    "validate_extended_profile_contracts.py",
    "validate_concrete_profile_consistency.py",
    "validate_review_followup_contracts.py",
    "validate_late_review_contracts.py",
)

SCRIPT_ROOT = Path(__file__).resolve().parent
BASE_ENVIRONMENT_KEYS = (
    "RUBYOPT",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
)


def base_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in BASE_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    return environment


def requested_validators(arguments: list[str]) -> list[tuple[str, bool]]:
    specifications = [(validator, True) for validator in DIRECT_VALIDATORS]
    specifications.extend(
        [(validator, True) for validator in DEFAULT_RULE_VALIDATORS]
        if not arguments
        else [(validator, False) for validator in arguments]
    )
    return specifications


def run_validators(
    validator_specs: list[tuple[str, bool]],
    environment: dict[str, str],
) -> int:
    seen_paths: set[Path] = set()
    for validator, bundled in validator_specs:
        path = (
            (SCRIPT_ROOT / validator).resolve()
            if bundled
            else Path(validator).expanduser().resolve()
        )
        if path in seen_paths:
            continue
        seen_paths.add(path)

        if not path.is_file():
            print(f"Missing profile validator: {validator}", file=sys.stderr)
            return 1

        completed = subprocess.run(
            [sys.executable, str(path)],
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode or 1

    print("All requested Agent Skill profile validators passed.")
    return 0


def git_worktree_state() -> tuple[str, str]:
    environment = base_environment()
    environment["LC_ALL"] = "C"
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        return "error", str(exc)

    output = completed.stdout
    if completed.returncode == 0 and output.strip() == "true":
        return "present", output
    if completed.returncode != 0 and "not a git repository" in output:
        return "absent", output
    return "error", output


def run(arguments: list[str] | None = None) -> int:
    effective_arguments = list(sys.argv[1:] if arguments is None else arguments)
    validator_specs = requested_validators(effective_arguments)
    state, diagnostic = git_worktree_state()

    if state == "present":
        return run_validators(validator_specs, base_environment())

    if state == "absent":
        with tempfile.TemporaryDirectory(
            prefix="profile-contract-git-index"
        ) as temporary:
            git_dir = Path(temporary) / "repository.git"
            environment = base_environment()
            completed = subprocess.run(
                ["git", "init", "--quiet", "--bare", str(git_dir)],
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if completed.returncode != 0:
                print(
                    "Unable to create a temporary Git index for archive "
                    f"validation: {completed.stdout.strip()}",
                    file=sys.stderr,
                )
                return 1

            environment.update(
                {
                    "GIT_DIR": str(git_dir),
                    "GIT_WORK_TREE": str(Path.cwd()),
                    "GIT_INDEX_FILE": str(git_dir / "index"),
                }
            )
            completed = subprocess.run(
                ["git", "read-tree", "--empty"],
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if completed.returncode != 0:
                print(
                    "Unable to initialize a temporary Git index for archive "
                    f"validation: {completed.stdout.strip()}",
                    file=sys.stderr,
                )
                return 1

            return run_validators(validator_specs, environment)

    print(
        "Unable to determine whether the skill root has Git metadata: "
        + diagnostic.strip(),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
