#!/usr/bin/env python3
"""Validate core Agent Skill profile contracts."""

from __future__ import annotations

import re
import subprocess
import sys

from lib.core_profile_interfaces import validate_interface_contracts
from lib.core_profile_runtime import validate_runtime_contracts
from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    RepositorySnapshot,
    SkillDocument,
)


def run() -> int:
    try:
        skill = SkillDocument.read("SKILL.md")
        selection = ProfileSelection.load("SKILL.md", document=skill)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    selected_profiles = list(selection.profiles)
    template_scaffold = selection.template_scaffold()
    repository = RepositorySnapshot()
    errors: list[str] = []

    allowed_profiles = [
        "instruction-only",
        "knowledge-augmented",
        "asset-driven",
        "script-assisted",
        "packaged-cli",
        "mcp-enabled",
        "browser-interface",
        "headless-service",
    ]

    name = skill.metadata.get("name")
    description = str(skill.metadata.get("description") or "")

    if template_scaffold:
        if name != "agent-skill-template":
            print(
                "'template-scaffold' is valid only for the uncustomized "
                "agent-skill-template.",
                file=sys.stderr,
            )
            return 1
    elif "template-scaffold" in selected_profiles:
        print(
            "'template-scaffold' cannot be combined with concrete skill profiles.",
            file=sys.stderr,
        )
        return 1

    if not template_scaffold:
        duplicates: list[str] = []
        for profile in selected_profiles:
            if selected_profiles.count(profile) > 1 and profile not in duplicates:
                duplicates.append(profile)
        if duplicates:
            errors.append(
                "SKILL.md contains duplicate selected profiles: "
                + ", ".join(duplicates)
            )

        invalid_profiles = [
            profile
            for profile in selected_profiles
            if profile not in allowed_profiles
        ]
        if invalid_profiles:
            errors.append(
                "SKILL.md contains unknown selected profiles: "
                + ", ".join(invalid_profiles)
            )

    profile_requirements = {
        "packaged-cli": [
            "RUNTIME.md",
            "INTERFACES.md",
            "CLI_INTERFACE.md",
        ],
        "mcp-enabled": [
            "RUNTIME.md",
            "INTERFACES.md",
            "MCP_INTERFACE.md",
            "docs/mcp-transports.md",
        ],
        "browser-interface": ["RUNTIME.md", "WEB_INTERFACE.md"],
        "headless-service": ["RUNTIME.md"],
    }

    resource_profile_requirements = {
        "references": "knowledge-augmented",
        "assets": "asset-driven",
        "scripts": "script-assisted",
        "mcp": "mcp-enabled",
    }

    if template_scaffold:
        customized_directories = [
            directory
            for directory in resource_profile_requirements
            if repository.operational_file_present(directory)
        ]
        if customized_directories:
            errors.append(
                "'template-scaffold' cannot be retained after adding operational "
                "files under: "
                + ", ".join(customized_directories)
                + "."
            )
    else:
        if name == "agent-skill-template" or "Template scaffold" in description:
            errors.append(
                "A concrete skill must replace the template name and description."
            )

        if (
            "instruction-only" in selected_profiles
            and len(selected_profiles) > 1
        ):
            errors.append(
                "'instruction-only' cannot be combined with resource, executable, "
                "or service profiles."
            )

        if re.search(r"\bTODO\b", skill.text, re.IGNORECASE):
            errors.append("A concrete SKILL.md must not retain TODO placeholders.")

        for heading in (
            "## Purpose",
            "## Use this skill when",
            "## Workflow",
            "## Output requirements",
            "## Validation",
            "## Safety and approval",
        ):
            content = skill.section(heading)
            if content is None or not content.strip():
                errors.append(
                    "A concrete SKILL.md requires non-empty content under "
                    f"'{heading}'."
                )

        for profile in selected_profiles:
            for required_path in profile_requirements.get(profile, []):
                if not repository.file(required_path):
                    errors.append(
                        f"Selected profile '{profile}' requires contract file: "
                        f"{required_path}"
                    )

        for directory, required_profile in resource_profile_requirements.items():
            if (
                repository.operational_file_present(directory)
                and required_profile not in selected_profiles
            ):
                errors.append(
                    f"Retained operational files under {directory}/ require "
                    f"selected profile '{required_profile}'."
                )

        supported_contracts = {
            "RUNTIME.md": [
                "script-assisted",
                "packaged-cli",
                "mcp-enabled",
                "browser-interface",
                "headless-service",
            ],
            "INTERFACES.md": ["packaged-cli", "mcp-enabled"],
            "CLI_INTERFACE.md": ["packaged-cli"],
            "MCP_INTERFACE.md": ["mcp-enabled"],
            "WEB_INTERFACE.md": ["browser-interface"],
        }
        for path, profiles in supported_contracts.items():
            if (
                repository._absolute(path).exists()
                and set(selected_profiles).isdisjoint(profiles)
            ):
                errors.append(
                    f"Retained contract {path} is unsupported by the selected "
                    "profiles."
                )

    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--stage",
            "-z",
            "--",
            "references",
            "assets",
            "scripts",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    index_output = completed.stdout.decode("utf-8", errors="replace")
    if completed.returncode == 0:
        for record in index_output.split("\0"):
            if not record:
                continue
            match = re.fullmatch(
                r"(\d+)\s+[0-9a-f]+\s+\d+\t(.+)", record, re.DOTALL
            )
            if match and match.group(1) == "160000":
                errors.append(
                    "Operational resource gitlinks are not allowed: "
                    + match.group(2)
                )
    else:
        errors.append(
            "Unable to inspect the Git index for operational resource gitlinks: "
            + index_output.strip()
        )

    validate_runtime_contracts(
        selected_profiles=selected_profiles,
        selection=selection,
        repository=repository,
        errors=errors,
    )
    validate_interface_contracts(
        selected_profiles=selected_profiles,
        selection=selection,
        repository=repository,
        errors=errors,
    )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Core Agent Skill profile contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
