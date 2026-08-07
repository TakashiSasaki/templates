#!/usr/bin/env python3
"""Validate review-follow-up Skill profile contracts."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    RepositorySnapshot,
    SkillDocument,
    ValuePolicy,
)


SOURCE_EXTENSIONS = {
    ".py", ".pyw", ".rb", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".go", ".rs", ".java", ".kt", ".kts", ".cs", ".fs", ".fsx", ".php",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".pl", ".pm", ".lua", ".r",
    ".swift", ".scala", ".clj", ".cljs", ".ex", ".exs", ".erl", ".hrl",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".m", ".mm", ".dart",
    ".groovy", ".gradle", ".bats", ".feature", ".t",
}
WINDOWS_EXECUTABLE_EXTENSIONS = {".com", ".exe", ".bat", ".cmd"}


def _is_executable_root_file(
    path: Path,
    *,
    platform_name: str = os.name,
) -> bool:
    """Apply portable executable semantics without Windows os.access false positives."""

    if platform_name == "nt":
        return path.suffix.casefold() in WINDOWS_EXECUTABLE_EXTENSIONS
    return os.access(path, os.X_OK)


def _extract_path(value: object | None) -> str | None:
    if not ValuePolicy.concrete(value):
        return None

    normalized = str(value)
    quoted = re.findall(r"`([^`]+)`", normalized)
    candidate: str | None = None
    if len(quoted) == 1:
        candidate = quoted[0]
    elif not quoted and re.fullmatch(r"\S+", normalized):
        candidate = ValuePolicy.strip_backticks(normalized)

    if candidate is None or candidate.startswith("/") or "\\" in candidate:
        return None
    if PureWindowsPath(candidate).drive:
        return None
    parts = PurePosixPath(candidate).parts
    if ".." in parts:
        return None
    return candidate


def run() -> int:
    try:
        skill = SkillDocument.read("SKILL.md")
        selection = ProfileSelection.load("SKILL.md", document=skill)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    repository = RepositorySnapshot()
    selected_profiles = set(selection.profiles)
    errors: list[str] = []

    root_implementation_files = [
        path
        for path in repository.root_files()
        if Path(path).suffix.lower() in SOURCE_EXTENSIONS
        or _is_executable_root_file(repository.root / path)
    ]

    if selection.template_scaffold():
        if root_implementation_files:
            errors.append(
                "'template-scaffold' cannot be retained after adding root-level "
                "implementation files: "
                + ", ".join(sorted(root_implementation_files))
                + "."
            )
    else:
        for heading in (
            "## Purpose",
            "## Use this skill when",
            "## Workflow",
            "## Output requirements",
            "## Validation",
            "## Safety and approval",
        ):
            section = skill.section(heading)
            if not ValuePolicy.concrete(section.strip() if section is not None else None):
                errors.append(
                    "A concrete SKILL.md requires non-sentinel operational content "
                    f"under '{heading}'."
                )

        application_profiles = {
            "packaged-cli",
            "mcp-enabled",
            "browser-interface",
            "headless-service",
        }
        if root_implementation_files and not selected_profiles.intersection(
            application_profiles
        ):
            errors.append(
                "Root-level implementation files require an application or service "
                "profile (packaged-cli, mcp-enabled, browser-interface, or "
                "headless-service): "
                + ", ".join(sorted(root_implementation_files))
                + "."
            )

        for profile, directory in {
            "knowledge-augmented": "references",
            "asset-driven": "assets",
            "script-assisted": "scripts",
        }.items():
            if selection.selected(profile) and not repository.operational_file_present(
                directory
            ):
                errors.append(
                    f"Selected profile '{profile}' requires at least one operational "
                    f"file under {directory}/."
                )

        for declaration in skill.declarations("Reference"):
            if declaration.path == "references/TODO.md":
                continue
            for field in ("Read when", "Provides"):
                if not ValuePolicy.concrete(declaration.fields.get(field)):
                    errors.append(
                        f"SKILL.md reference declaration for {declaration.path} must "
                        f"include a concrete '{field}:' value."
                    )

        if selection.selected("mcp-enabled"):
            runtime = repository.document("RUNTIME.md")
            if runtime is None:
                errors.append("Selected profile 'mcp-enabled' requires RUNTIME.md.")
            else:
                protocol = runtime.section("## MCP protocol support")
                for item in (
                    "Supported protocol revisions",
                    "Supported protocol eras",
                    "Default revision or negotiation mode",
                    "MCP SDK or protocol library",
                    "SDK version",
                    "Legacy compatibility policy",
                    "JSON Schema dialects",
                    "Deprecated feature policy",
                    "Negotiation and compatibility tests",
                ):
                    if not ValuePolicy.concrete(
                        runtime.table_value(item, section=protocol)
                    ):
                        errors.append(
                            "Selected profile 'mcp-enabled' requires a concrete "
                            f"'{item}' value in RUNTIME.md."
                        )

                if not ValuePolicy.resolved(
                    runtime.table_value("Optional MCP extensions", section=protocol)
                ):
                    errors.append(
                        "Selected profile 'mcp-enabled' must resolve 'Optional MCP "
                        "extensions' to a concrete list or NONE in RUNTIME.md."
                    )

                http = runtime.section("### Streamable HTTP variant")
                if runtime.table_value("Supported", section=http) == "YES":
                    for item in (
                        "Authentication",
                        "Host-header validation",
                        "Origin validation granularity",
                        "Allowed origins and absent-Origin policy",
                        "Connection-reuse security tests",
                    ):
                        if not ValuePolicy.concrete(
                            runtime.table_value(item, section=http)
                        ):
                            errors.append(
                                "Supported Streamable HTTP requires a concrete "
                                f"'{item}' security decision in RUNTIME.md; absence "
                                "sentinels are not allowed."
                            )

        if selection.selected("packaged-cli"):
            if not repository.code_artifact_present("src"):
                errors.append(
                    "Selected profile 'packaged-cli' requires at least one "
                    "non-guidance regular source artifact under src/."
                )
            if not repository.code_artifact_present("tests"):
                errors.append(
                    "Selected profile 'packaged-cli' requires at least one "
                    "non-guidance regular test artifact under tests/."
                )

            runtime = repository.document("RUNTIME.md")
            if runtime is None:
                errors.append("Selected profile 'packaged-cli' requires RUNTIME.md.")
            else:
                primary = runtime.section("## Primary implementation")
                manifest_path = _extract_path(
                    runtime.table_value("Project manifest", section=primary)
                )
                if not (
                    manifest_path
                    and repository.file(manifest_path)
                    and not repository.symlink(manifest_path)
                ):
                    errors.append(
                        "Selected profile 'packaged-cli' requires 'Project manifest' "
                        "to name one retained regular file by exact relative path."
                    )

                lockfile_path = _extract_path(
                    runtime.table_value("Lockfile policy", section=primary)
                )
                if not (
                    lockfile_path
                    and repository.file(lockfile_path)
                    and not repository.symlink(lockfile_path)
                ):
                    errors.append(
                        "Selected profile 'packaged-cli' requires 'Lockfile policy' "
                        "to include one retained lockfile path, preferably in backticks."
                    )

                if (
                    manifest_path
                    and lockfile_path
                    and manifest_path == lockfile_path
                ):
                    errors.append(
                        "Selected profile 'packaged-cli' must use distinct retained "
                        "manifest and lockfile files."
                    )

                cli = repository.document("CLI_INTERFACE.md")
                if cli is not None:
                    commands = runtime.section("## Commands")
                    runtime_command = runtime.table_value(
                        "Human CLI", section=commands
                    )
                    human_cli = cli.section("## Human CLI")
                    interface_command = cli.field("Command", section=human_cli)
                    if (
                        ValuePolicy.concrete(runtime_command)
                        and ValuePolicy.concrete(interface_command)
                        and runtime_command != interface_command
                    ):
                        errors.append(
                            "The packaged CLI command must match between RUNTIME.md "
                            f"('{runtime_command}') and CLI_INTERFACE.md "
                            f"('{interface_command}')."
                        )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Review follow-up Agent Skill contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
