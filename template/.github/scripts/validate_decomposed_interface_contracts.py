#!/usr/bin/env python3
"""Validate decomposed CLI and MCP interface contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_PATH = Path("SKILL.md")


def strip_backticks(value: object | None) -> str:
    normalized = "" if value is None else str(value).strip()
    if (
        len(normalized) >= 2
        and normalized.startswith("`")
        and normalized.endswith("`")
    ):
        return normalized[1:-1]
    return normalized


def resolved_value(value: str | None) -> bool:
    return bool(
        value
        and value.strip()
        and not re.search(r"\b(?:TODO|UNSELECTED)\b", value, re.IGNORECASE)
    )


def concrete_value(value: str | None) -> bool:
    return bool(
        resolved_value(value)
        and not re.fullmatch(
            r"(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))",
            value.strip(),
            re.IGNORECASE,
        )
    )


def concrete_section(value: str | None) -> bool:
    if not resolved_value(value):
        return False

    substantive_lines = [
        line.strip()
        for line in value.splitlines()
        if line.strip() and not re.match(r"^```", line.strip())
    ]
    normalized = re.sub(r"\s+", " ", " ".join(substantive_lines)).strip()

    placeholder_marker = re.compile(
        r"\b(?:TBD|FIXME|PLACEHOLDER)\b", re.IGNORECASE
    )
    placeholder_phrase = re.compile(
        r"\b(?:details?|behavior|contract|implementation|documentation)\s+"
        r"(?:forthcoming|pending|to\s+follow|will\s+be\s+"
        r"(?:added|defined|documented|specified)(?:\s+later)?|to\s+be\s+"
        r"(?:added|defined|documented|specified|determined|decided))\b|"
        r"\bto\s+be\s+(?:decided|determined|defined|documented|specified)\b|"
        r"\bwill\s+be\s+documented\s+later\b",
        re.IGNORECASE,
    )
    guidance_line = re.compile(
        r"^(?:describe|document|specify|select|define|explain|replace|complete|"
        r"state|decide|record)\b",
        re.IGNORECASE,
    )

    if placeholder_marker.search(normalized) or placeholder_phrase.search(normalized):
        return False

    guidance_only = bool(substantive_lines) and all(
        guidance_line.search(re.sub(r"^[-*]\s*", "", line))
        for line in substantive_lines
    )
    return not guidance_only


def markdown_section(document: str, heading: str) -> str | None:
    match = re.match(r"^#+", heading)
    if match is None:
        raise ValueError(f"heading must begin with '#': {heading!r}")
    level = len(match.group(0))
    boundary = r"^##\s|\Z" if level == 2 else r"^(?:##|###)\s|\Z"
    section_match = re.search(
        rf"^{re.escape(heading)}\s*$\n(.*?)(?={boundary})",
        document,
        re.MULTILINE | re.DOTALL,
    )
    return section_match.group(1) if section_match else None


def field_value(section: str | None, label: str) -> str | None:
    if section is None:
        return None
    match = re.search(
        rf"^{re.escape(label)}:\s*(.*?)\s*$", section, re.MULTILINE
    )
    return strip_backticks(match.group(1)) if match else None


def table_value(section: str | None, item: str) -> str | None:
    if section is None:
        return None
    match = re.search(
        rf"^\|\s*{re.escape(item)}\s*\|\s*(.*?)\s*\|\s*$",
        section,
        re.MULTILINE,
    )
    return strip_backticks(match.group(1)) if match else None


def support_token(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return re.split(r"[;\s]", stripped, maxsplit=1)[0].upper()


def run() -> int:
    if not SKILL_PATH.is_file():
        print("Missing universally required file: SKILL.md", file=sys.stderr)
        return 1

    profile_values: list[str] = []
    for raw_line in SKILL_PATH.read_text(encoding="utf-8").splitlines():
        normalized = raw_line.strip()
        if normalized.startswith("- "):
            normalized = normalized[2:].strip()
        match = re.fullmatch(r"Selected profiles:\s*(.+?)\s*", normalized)
        if match:
            profile_values.append(strip_backticks(match.group(1)))

    if len(profile_values) != 1:
        print(
            "SKILL.md must contain exactly one 'Selected profiles:' declaration.",
            file=sys.stderr,
        )
        return 1

    selected_profiles = [
        profile.strip()
        for profile in profile_values[0].split(",")
        if profile.strip()
    ]
    if selected_profiles == ["template-scaffold"]:
        print(
            "Decomposed public interface contracts are valid for the template scaffold."
        )
        return 0

    errors: list[str] = []

    required_contracts = {
        "packaged-cli": "CLI_INTERFACE.md",
        "mcp-enabled": "MCP_INTERFACE.md",
    }
    for profile, path in required_contracts.items():
        if profile in selected_profiles and not Path(path).is_file():
            errors.append(
                f"Selected profile '{profile}' requires contract file: {path}"
            )

    for path, profiles in {
        "CLI_INTERFACE.md": {"packaged-cli"},
        "MCP_INTERFACE.md": {"mcp-enabled"},
    }.items():
        if Path(path).exists() and set(selected_profiles).isdisjoint(profiles):
            errors.append(
                f"Retained contract {path} is unsupported by the selected profiles."
            )

    def validate_common_contract(
        path: str, required_headings: tuple[str, ...]
    ) -> str | None:
        contract = Path(path)
        if not contract.is_file():
            return None

        document = contract.read_text(encoding="utf-8")
        status = field_value(document, "Selection status")
        if status != "SELECTED":
            errors.append(
                f"Selected contract {path} requires 'Selection status: SELECTED'."
            )

        if re.search(r"\b(?:TODO|UNSELECTED)\b", document, re.IGNORECASE):
            errors.append(
                f"Selected contract {path} must not retain TODO or UNSELECTED "
                "placeholders."
            )

        for heading in required_headings:
            section = markdown_section(document, heading)
            if not concrete_section(section):
                errors.append(
                    f"Selected contract {path} requires concrete, non-placeholder "
                    f"content under '{heading}'."
                )

        return document

    if "packaged-cli" in selected_profiles:
        cli = validate_common_contract(
            "CLI_INTERFACE.md",
            (
                "## Status",
                "## Human CLI",
                "## In-place agent launcher",
                "## Inputs, outputs, and side effects",
                "## Compatibility and versioning",
                "## Semantic-equivalence and test requirements",
                "## Decision rationale",
            ),
        )

        if cli is not None:
            human_cli = markdown_section(cli, "## Human CLI")
            for label in (
                "Command",
                "Working directory",
                "Format",
                "Contract version field",
            ):
                if not concrete_value(field_value(human_cli, label)):
                    errors.append(
                        "Selected contract CLI_INTERFACE.md requires a concrete "
                        f"'{label}:' value."
                    )

            launcher = markdown_section(cli, "## In-place agent launcher")
            launcher_support = support_token(field_value(launcher, "Supported"))
            if launcher_support not in {"YES", "NO"}:
                errors.append(
                    "CLI_INTERFACE.md must set the in-place launcher 'Supported:' "
                    "value to YES or NO."
                )
            for label in ("Command", "Delegates to"):
                value = field_value(launcher, label)
                valid = (
                    concrete_value(value)
                    if launcher_support == "YES"
                    else resolved_value(value)
                )
                if not valid:
                    errors.append(
                        "CLI_INTERFACE.md requires a resolved "
                        f"'{label}:' value for the selected launcher support state."
                    )

            io_contract = markdown_section(
                cli, "## Inputs, outputs, and side effects"
            )
            absence_allowed = {
                "Files or external state modified",
                "Network access",
                "Required permissions",
            }
            for item in (
                "Input forms and precedence",
                "Standard output",
                "Standard error",
                "Files or external state modified",
                "Network access",
                "Required permissions",
                "Confirmation policy",
                "Timeout and cancellation",
                "Idempotency and retry behavior",
            ):
                value = table_value(io_contract, item)
                valid = (
                    resolved_value(value)
                    if item in absence_allowed
                    else concrete_value(value)
                )
                if not valid:
                    errors.append(
                        f"CLI_INTERFACE.md requires a resolved '{item}' behavior."
                    )

            compatibility = markdown_section(
                cli, "## Compatibility and versioning"
            )
            for label in (
                "Compatibility policy",
                "Deprecation policy",
                "Structured contract version source",
            ):
                if not concrete_value(field_value(compatibility, label)):
                    errors.append(
                        f"CLI_INTERFACE.md requires a concrete '{label}:' value."
                    )

            rationale = markdown_section(cli, "## Decision rationale")
            if not concrete_value(field_value(rationale, "Rationale")):
                errors.append(
                    "CLI_INTERFACE.md requires a concrete 'Rationale:' value."
                )

    if "mcp-enabled" in selected_profiles:
        caller_behavior_headings = (
            "### Tool inventory, schemas, and caching",
            "### Lossless paginated tool-list output",
            "### Tool-call results and errors",
            "### Multiple calls and application state",
            "### Selected modern multi-round-trip requests",
            "### Selected initialization-era server-to-client requests",
            "### Cancellation, tasks, and extensions",
            "### Ownership and workspace policy",
        )

        mcp = validate_common_contract(
            "MCP_INTERFACE.md",
            (
                "## Status",
                "## MCP protocol reference",
                "## stdio MCP server variant",
                "## Streamable HTTP MCP server variant",
                "## Bundled ad hoc MCP tool client",
                *caller_behavior_headings,
                "## Semantic-equivalence and test requirements",
                "## Decision rationale",
            ),
        )

        if mcp is not None:
            protocol = markdown_section(mcp, "## MCP protocol reference")
            for label in (
                "Public negotiation and fallback behavior",
                "Public compatibility statement",
            ):
                if not concrete_value(field_value(protocol, label)):
                    errors.append(
                        f"MCP_INTERFACE.md requires a concrete '{label}:' value."
                    )

            variants = {
                "stdio": {
                    "heading": "## stdio MCP server variant",
                    "fields": ("Launch command", "Lifecycle owner"),
                    "allow_not_supported": (),
                },
                "Streamable HTTP": {
                    "heading": "## Streamable HTTP MCP server variant",
                    "fields": (
                        "Start command",
                        "Stop command or shutdown method",
                        "Endpoint URL",
                        "Bind address",
                        "Port selection",
                        "Supported protocol eras",
                        "Revision-specific state model",
                        "Authentication",
                        "Health/readiness check",
                    ),
                    "allow_not_supported": (),
                },
                "bundled MCP client": {
                    "heading": "## Bundled ad hoc MCP tool client",
                    "fields": (
                        "Scope",
                        "Command",
                        "Transport used",
                        "Negotiation and compatibility behavior",
                        "Invocation scope",
                        "Interaction modes",
                        "Task or extension support",
                    ),
                    "allow_not_supported": ("Task or extension support",),
                },
            }

            support_values: dict[str, str | None] = {}
            for variant, specification in variants.items():
                section = markdown_section(mcp, specification["heading"])
                support = support_token(field_value(section, "Supported"))
                support_values[variant] = support
                if support not in {"YES", "NO"}:
                    errors.append(
                        f"MCP_INTERFACE.md must set '{variant}' Supported to YES or NO."
                    )

                for label in specification["fields"]:
                    value = field_value(section, label)
                    allow_not_supported = label in specification["allow_not_supported"]
                    if support == "YES":
                        valid = (
                            resolved_value(value)
                            if allow_not_supported
                            else concrete_value(value)
                        )
                    else:
                        valid = resolved_value(value)
                    if not valid:
                        errors.append(
                            "MCP_INTERFACE.md requires a resolved "
                            f"'{label}:' value for '{variant}'."
                        )

            if "YES" not in (
                support_values.get("stdio"),
                support_values.get("Streamable HTTP"),
            ):
                errors.append(
                    "Selected profile 'mcp-enabled' requires at least one "
                    "supported MCP server variant in MCP_INTERFACE.md."
                )

            rationale = markdown_section(mcp, "## Decision rationale")
            if not concrete_value(field_value(rationale, "Rationale")):
                errors.append(
                    "MCP_INTERFACE.md requires a concrete 'Rationale:' value."
                )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Decomposed public interface contracts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
