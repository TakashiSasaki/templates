"""Interface contract checks for the core Skill validator."""

from __future__ import annotations

import re

from .profile_contracts import ProfileSelection, RepositorySnapshot, ValuePolicy, support_token


def validate_interface_contracts(
    *,
    selected_profiles: list[str],
    selection: ProfileSelection,
    repository: RepositorySnapshot,
    errors: list[str],
) -> None:
    routing = repository.document("INTERFACES.md")
    if (
        set(selected_profiles) & {"packaged-cli", "mcp-enabled"}
        and routing is not None
    ):
        preferred_interface = routing.field("Preferred agent interface")
        if not ValuePolicy.resolved(preferred_interface):
            errors.append(
                "Selected CLI or MCP profiles require a concrete "
                "'Preferred agent interface:' in INTERFACES.md."
            )

    if selection.selected("packaged-cli"):
        cli = repository.document("CLI_INTERFACE.md")
        if cli is not None:
            human_cli = cli.section("## Human CLI")
            if human_cli is None:
                errors.append(
                    "Selected profile 'packaged-cli' requires a "
                    "'## Human CLI' contract in CLI_INTERFACE.md."
                )
            else:
                descriptions = {
                    "Command": "canonical command",
                    "Working directory": "working directory",
                    "Format": "structured output format",
                    "Contract version field": (
                        "structured output contract version"
                    ),
                }
                for label, description_text in descriptions.items():
                    if not ValuePolicy.concrete(
                        cli.field(label, section=human_cli)
                    ):
                        errors.append(
                            "Selected profile 'packaged-cli' requires a concrete "
                            f"{description_text} in CLI_INTERFACE.md."
                        )

    if selection.selected("mcp-enabled"):
        mcp = repository.document("MCP_INTERFACE.md")
        if mcp is not None:
            protocol_reference = mcp.section("## MCP protocol reference")
            if protocol_reference is None:
                errors.append(
                    "Selected profile 'mcp-enabled' requires an MCP protocol "
                    "reference contract in MCP_INTERFACE.md."
                )
            else:
                for label in (
                    "Public negotiation and fallback behavior",
                    "Public compatibility statement",
                ):
                    if not ValuePolicy.resolved(
                        mcp.field(label, section=protocol_reference)
                    ):
                        errors.append(
                            "Selected profile 'mcp-enabled' requires a concrete "
                            f"'{label}:' value in MCP_INTERFACE.md."
                        )

            support_values = mcp.support_values()
            if not support_values or not any(
                support_token(value) == "YES"
                for value in support_values
            ):
                errors.append(
                    "Selected profile 'mcp-enabled' requires at least one MCP "
                    "interface with 'Supported: YES' in MCP_INTERFACE.md."
                )
            if any(
                re.search(r"\bUNSELECTED\b", value, re.IGNORECASE)
                for value in support_values
            ):
                errors.append(
                    "Selected profile 'mcp-enabled' must resolve every retained "
                    "MCP 'Supported:' field in MCP_INTERFACE.md."
                )

    if selection.selected("browser-interface"):
        web = repository.document("WEB_INTERFACE.md")
        if web is not None:
            if re.search(
                r"\b(?:TODO|UNSELECTED)\b", web.text, re.IGNORECASE
            ):
                errors.append(
                    "Selected profile 'browser-interface' must resolve every "
                    "TODO and UNSELECTED value in WEB_INTERFACE.md."
                )
            if web.field("Supported") != "YES":
                errors.append(
                    "Selected profile 'browser-interface' requires "
                    "'Supported: YES' in WEB_INTERFACE.md."
                )
            for label in ("Purpose", "Default enablement", "Production policy"):
                if not ValuePolicy.resolved(web.field(label)):
                    errors.append(
                        "Selected profile 'browser-interface' requires a concrete "
                        f"'{label}:' value in WEB_INTERFACE.md."
                    )

            for label in (
                "External base URL",
                "Web UI path or URL",
                "MCP endpoint visible to the browser",
                "MCP endpoint used by the UI backend",
                "Authentication",
                "Allowed users or network boundary",
                "Read-only operations",
                "Mutating operations",
                "Destructive operations",
                "Confirmation policy",
                "Sensitive argument masking",
                "Sensitive result masking",
                "Audit logging",
                "Web health behavior",
                "Failure relationship",
            ):
                if not ValuePolicy.resolved(web.field(label)):
                    errors.append(
                        "Selected profile 'browser-interface' requires a concrete "
                        f"'{label}:' value in WEB_INTERFACE.md."
                    )

            relationship = web.section("## Relationship to MCP")
            interaction_values = [
                web.list_field(label, section=relationship)
                or web.field(label, section=relationship)
                for label in (
                    "backend acts as an MCP client",
                    "browser calls MCP directly",
                    "UI uses a non-MCP application API",
                    "mixed model",
                )
            ]
            if not any(
                value == "YES"
                or (ValuePolicy.resolved(value) and value != "NO")
                for value in interaction_values
            ):
                errors.append(
                    "Selected profile 'browser-interface' requires one concrete "
                    "UI interaction model in WEB_INTERFACE.md."
                )

            capabilities = web.section("## UI capabilities")
            if capabilities is None or re.search(
                r"\b(?:TODO|UNSELECTED)\b",
                capabilities,
                re.IGNORECASE,
            ):
                errors.append(
                    "Selected profile 'browser-interface' must resolve every UI "
                    "capability field in WEB_INTERFACE.md."
                )

            required_tests = web.section("## Required tests")
            if required_tests is None or not required_tests.strip():
                errors.append(
                    "Selected profile 'browser-interface' requires a non-empty "
                    "Required tests section in WEB_INTERFACE.md."
                )

            rationale = web.section("## Decision rationale")
            if (
                rationale is None
                or not rationale.strip()
                or re.search(r"\bTODO\b", rationale, re.IGNORECASE)
            ):
                errors.append(
                    "Selected profile 'browser-interface' requires a concrete "
                    "decision rationale in WEB_INTERFACE.md."
                )
