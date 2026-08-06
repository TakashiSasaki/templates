#!/usr/bin/env python3
"""Validate extended Agent Skill profile contracts."""

from __future__ import annotations

import re
import sys

from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    RepositorySnapshot,
    SkillDocument,
    ValuePolicy,
    support_token,
)


def run() -> int:
    try:
        skill = SkillDocument.read("SKILL.md")
        selection = ProfileSelection.load("SKILL.md", document=skill)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    repository = RepositorySnapshot()
    selected_profiles = list(selection.profiles)
    errors: list[str] = []

    if selection.template_scaffold():
        scaffold_directories = [
            "references",
            "assets",
            "scripts",
            "mcp",
            "src",
            "app",
            "lib",
            "bin",
            "server",
            "client",
            "tests",
            "web",
            "website",
            "frontend",
            "ui",
            "public",
            "static",
            "www",
        ]
        customized = [
            directory
            for directory in scaffold_directories
            if repository.operational_file_present(directory)
        ]
        manifests = [
            path
            for path in (
                "package.json",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "bun.lock",
                "bun.lockb",
                "pyproject.toml",
                "requirements.txt",
                "uv.lock",
                "Pipfile",
                "Pipfile.lock",
                "Cargo.toml",
                "Cargo.lock",
                "go.mod",
                "go.sum",
                "Gemfile",
                "Gemfile.lock",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "composer.json",
                "composer.lock",
            )
            if repository.file(path)
        ]
        roots = [
            path
            for path in (
                "index.html",
                "service-worker.js",
                "sw.js",
                "manifest.webmanifest",
                "Dockerfile",
                "compose.yml",
                "compose.yaml",
                "docker-compose.yml",
                "docker-compose.yaml",
            )
            if repository.file(path)
        ]

        if customized:
            errors.append(
                "'template-scaffold' cannot be retained after adding "
                "implementation or operational files under: "
                + ", ".join(customized)
                + "."
            )
        if manifests:
            errors.append(
                "'template-scaffold' cannot be retained after adding runtime or "
                "package manifests: "
                + ", ".join(manifests)
                + "."
            )
        if roots:
            errors.append(
                "'template-scaffold' cannot be retained after adding root "
                "implementation or deployment files: "
                + ", ".join(roots)
                + "."
            )
        if skill.metadata.get("name") != "agent-skill-template":
            errors.append(
                "'template-scaffold' is valid only while the skill name remains "
                "'agent-skill-template'."
            )

    for declaration in skill.declarations("Script"):
        if declaration.path == "scripts/TODO":
            continue

        required_fields = [
            "Run when",
            "Exact invocation",
            "Working directory",
            "Inputs and arguments",
            "Stdout/result",
            "Stderr/diagnostics",
            "Exit status",
            "Files or external state modified",
            "Network access",
            "Required permissions",
            "Automatic execution allowed",
            "Human confirmation required",
            "Idempotency and retry behavior",
        ]
        allow_none = {
            "Inputs and arguments",
            "Files or external state modified",
            "Network access",
            "Required permissions",
        }

        for field in required_fields:
            value = declaration.fields.get(field)
            valid = (
                ValuePolicy.resolved(value)
                if field in allow_none
                else ValuePolicy.concrete(value)
            )
            if not valid:
                errors.append(
                    f"SKILL.md script declaration for {declaration.path} must "
                    f"include a concrete '{field}:' value."
                )

        for field in (
            "Automatic execution allowed",
            "Human confirmation required",
        ):
            value = declaration.fields.get(field)
            if (
                ValuePolicy.resolved(value)
                and str(value).upper()
                not in {"YES", "NO", "WITH CONDITIONS"}
            ):
                errors.append(
                    f"SKILL.md script declaration for {declaration.path} must "
                    f"set '{field}:' to YES, NO, or WITH CONDITIONS."
                )

    runtime_profiles = {
        "script-assisted",
        "packaged-cli",
        "mcp-enabled",
        "browser-interface",
        "headless-service",
    }
    runtime = repository.document("RUNTIME.md")
    if set(selected_profiles) & runtime_profiles and runtime is not None:
        primary = runtime.section("## Primary implementation")
        for item in (
            "Language",
            "Runtime",
            "Minimum runtime version",
            "Source layout",
            "Supported operating systems",
        ):
            if not ValuePolicy.concrete(
                runtime.table_value(item, section=primary)
            ):
                errors.append(
                    "Selected runtime-backed profiles require a concrete "
                    f"'{item}' value in RUNTIME.md."
                )

    if selection.selected("browser-interface"):
        web = repository.document("WEB_INTERFACE.md")
        if web is not None:
            relationship = web.section("## Relationship to MCP")
            models = {
                label: (
                    web.list_field(label, section=relationship).upper()
                    if web.list_field(label, section=relationship) is not None
                    else None
                )
                for label in (
                    "backend acts as an MCP client",
                    "browser calls MCP directly",
                    "UI uses a non-MCP application API",
                    "mixed model",
                )
            }

            if not all(value in {"YES", "NO"} for value in models.values()):
                errors.append(
                    "WEB_INTERFACE.md must set every UI interaction model to "
                    "YES or NO."
                )
            if list(models.values()).count("YES") != 1:
                errors.append(
                    "WEB_INTERFACE.md must select exactly one UI interaction "
                    "model with YES."
                )

    if selection.selected("mcp-enabled"):
        mcp = repository.document("MCP_INTERFACE.md")
        runtime = repository.document("RUNTIME.md")
        if mcp is not None:
            variants = {
                "stdio": {
                    "heading": "## stdio MCP server variant",
                    "runtime_heading": "### stdio variant",
                    "mandatory": ["Launch command", "Lifecycle owner"],
                    "allow_not_supported": [],
                },
                "Streamable HTTP": {
                    "heading": "## Streamable HTTP MCP server variant",
                    "runtime_heading": "### Streamable HTTP variant",
                    "mandatory": [
                        "Start command",
                        "Stop command or shutdown method",
                        "Endpoint URL",
                        "Bind address",
                        "Port selection",
                        "Supported protocol eras",
                        "Revision-specific state model",
                        "Authentication",
                        "Health/readiness check",
                    ],
                    "allow_not_supported": [],
                },
                "bundled MCP client": {
                    "heading": "## Bundled ad hoc MCP tool client",
                    "runtime_heading": "### Bundled ad hoc MCP tool client",
                    "mandatory": [
                        "Scope",
                        "Command",
                        "Transport used",
                        "Negotiation and compatibility behavior",
                        "Invocation scope",
                        "Interaction modes",
                        "Task or extension support",
                    ],
                    "allow_not_supported": ["Task or extension support"],
                },
            }

            supported_server_variants: list[str] = []
            for variant_name, specification in variants.items():
                section = mcp.section(specification["heading"])
                if section is None:
                    errors.append(
                        "Selected profile 'mcp-enabled' requires "
                        f"'{specification['heading']}' in MCP_INTERFACE.md."
                    )
                    continue

                interface_support = support_token(
                    mcp.field("Supported", section=section)
                )
                if interface_support not in {"YES", "NO"}:
                    errors.append(
                        f"MCP interface '{variant_name}' must set 'Supported:' "
                        "to YES or NO in MCP_INTERFACE.md."
                    )
                    continue

                if runtime is not None:
                    runtime_section = runtime.section(
                        specification["runtime_heading"]
                    )
                    runtime_support = support_token(
                        runtime.table_value(
                            "Supported", section=runtime_section
                        )
                    )
                    if runtime_support not in {"YES", "NO"}:
                        errors.append(
                            f"MCP variant '{variant_name}' must set Supported "
                            "to YES or NO in RUNTIME.md."
                        )
                    if (
                        runtime_support in {"YES", "NO"}
                        and interface_support != runtime_support
                    ):
                        errors.append(
                            f"MCP variant '{variant_name}' has inconsistent "
                            "Supported values between RUNTIME.md and "
                            "MCP_INTERFACE.md."
                        )

                if interface_support != "YES":
                    continue

                if variant_name != "bundled MCP client":
                    supported_server_variants.append(variant_name)
                if re.search(
                    r"\b(?:TODO|UNSELECTED)\b",
                    section,
                    re.IGNORECASE,
                ):
                    errors.append(
                        f"Supported MCP interface '{variant_name}' must not "
                        "retain TODO or UNSELECTED fields in MCP_INTERFACE.md."
                    )

                for label in specification["mandatory"]:
                    value = mcp.field(label, section=section)
                    valid = (
                        ValuePolicy.resolved(value)
                        if label in specification["allow_not_supported"]
                        else ValuePolicy.concrete(value)
                    )
                    if not valid:
                        errors.append(
                            f"Supported MCP interface '{variant_name}' requires "
                            f"a concrete '{label}:' value in MCP_INTERFACE.md."
                        )

            if not supported_server_variants:
                errors.append(
                    "Selected profile 'mcp-enabled' requires at least one "
                    "supported MCP server variant in MCP_INTERFACE.md."
                )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Extended Agent Skill profile contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
