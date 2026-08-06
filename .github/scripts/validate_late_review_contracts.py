#!/usr/bin/env python3
"""Validate language-neutral root signals and late-review MCP requirements."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    RepositorySnapshot,
    SkillDocument,
    ValuePolicy,
)


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

    ignored_root_names = {
        "README.md",
        "SKILL.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "RUNTIME.md",
        "INTERFACES.md",
        "CLI_INTERFACE.md",
        "MCP_INTERFACE.md",
        "WEB_INTERFACE.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.template",
        "COPYING",
        "COPYING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "CHANGELOG.md",
    }
    ignored_root_names_casefold = {name.casefold() for name in ignored_root_names}
    guidance_extensions = {
        ".md",
        ".markdown",
        ".mdx",
        ".rst",
        ".adoc",
        ".asciidoc",
        ".txt",
        ".pdf",
    }

    root_implementation_files = [
        path
        for path in repository.root_files()
        if not path.startswith(".")
        and path.casefold() not in ignored_root_names_casefold
        and Path(path).suffix.lower() not in guidance_extensions
    ]

    if selection.template_scaffold() and root_implementation_files:
        errors.append(
            "'template-scaffold' cannot be retained after adding language-neutral "
            "root implementation signals: "
            f"{', '.join(sorted(root_implementation_files))}."
        )
    elif not selection.template_scaffold():
        application_profiles = {
            "packaged-cli",
            "mcp-enabled",
            "browser-interface",
            "headless-service",
        }
        if root_implementation_files and selected_profiles.isdisjoint(application_profiles):
            errors.append(
                "Language-neutral root implementation files require an application "
                "or service profile: "
                f"{', '.join(sorted(root_implementation_files))}."
            )

    if selection.selected("mcp-enabled"):
        runtime = repository.document("RUNTIME.md")
        if runtime is not None:
            protocol = runtime.section("## MCP protocol support")
            revisions = runtime.table_value(
                "Supported protocol revisions", section=protocol
            ) or ""

            stdio = runtime.section("### stdio variant")
            if runtime.table_value("Supported", section=stdio) == "YES":
                for item in (
                    "Server entry point",
                    "Lifecycle owner",
                    "Invocation scope",
                    "Protocol negotiation/discovery",
                    "Request metadata behavior",
                    "Startup cost policy",
                    "Cancellation behavior",
                    "Child-process shutdown and escalation",
                ):
                    if not ValuePolicy.concrete(
                        runtime.table_value(item, section=stdio)
                    ):
                        errors.append(
                            "Supported stdio requires a concrete "
                            f"'{item}' runtime value; NOT SUPPORTED is reserved "
                            "for Supported: NO."
                        )

            http = runtime.section("### Streamable HTTP variant")
            http_supported = (
                runtime.table_value("Supported", section=http) == "YES"
            )
            if http_supported:
                for item in (
                    "Server entry point",
                    "Endpoint path",
                    "Default bind address",
                    "Port",
                    "Supported protocol eras",
                    "Revision-specific state model",
                    "Concurrent-client policy",
                    "Authentication",
                    "Host-header validation",
                    "Origin validation granularity",
                    "Allowed origins and absent-Origin policy",
                    "Connection-reuse security tests",
                    "Readiness check",
                    "Cancellation behavior",
                    "Shutdown/restart policy",
                    "Non-loopback support",
                ):
                    if not ValuePolicy.concrete(
                        runtime.table_value(item, section=http)
                    ):
                        errors.append(
                            "Supported Streamable HTTP requires a concrete "
                            f"'{item}' runtime value; NOT SUPPORTED is reserved "
                            "for Supported: NO."
                        )

            if http_supported and "2026-07-28" in revisions:
                modern_table: str | None = None
                if http is not None:
                    match = re.search(
                        r"When `2026-07-28` is supported, also complete:\s*\n\n"
                        r"(.*?)(?=\nThe stdio and Streamable HTTP variants|\Z)",
                        http,
                        re.DOTALL,
                    )
                    if match:
                        modern_table = match.group(1)

                for item in (
                    "POST request model",
                    "`Accept: application/json, text/event-stream`",
                    "`MCP-Protocol-Version` and request `_meta` consistency",
                    "Required `Mcp-Method` and conditional `Mcp-Name` headers",
                    "Header value encoding",
                    "`x-mcp-header` validation and `Mcp-Param-*` emission",
                    "JSON and request-scoped SSE response handling",
                    "SSE-stream cancellation",
                    "`Mcp-Session-Id`, GET, DELETE, and resumability",
                ):
                    if not ValuePolicy.concrete(
                        runtime.table_value(item, section=modern_table)
                    ):
                        errors.append(
                            "Protocol revision 2026-07-28 with Streamable HTTP "
                            "requires a concrete modern transport value for "
                            f"'{item}'."
                        )

                fallback = runtime.table_value(
                    "Initialization-era fallback on the same endpoint",
                    section=modern_table,
                )
                if not ValuePolicy.resolved_allow_not_supported(fallback):
                    errors.append(
                        "Protocol revision 2026-07-28 requires a resolved "
                        "initialization-era fallback decision; NOT SUPPORTED is "
                        "allowed, NONE is not."
                    )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Late-review Agent Skill contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
