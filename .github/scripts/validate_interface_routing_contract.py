#!/usr/bin/env python3
"""Validate the public interface routing contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_PATH = Path("SKILL.md")
ROUTING_PATH = Path("INTERFACES.md")
PUBLIC_INTERFACE_PROFILES = {"packaged-cli", "mcp-enabled"}
ROUTE_LABELS = (
    "native MCP tool already registered in the host",
    "existing Streamable HTTP MCP endpoint",
    "bundled ad hoc MCP tool client over stdio or Streamable HTTP",
    "stable in-place CLI launcher",
    "installed human CLI command",
    "browser Web interface",
)


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


def normalize_route(value: object | None) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value).strip()).lower()


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
        print("Public interface routing contract is valid for the template scaffold.")
        return 0

    routing_selected = bool(set(selected_profiles) & PUBLIC_INTERFACE_PROFILES)
    errors: list[str] = []

    if not routing_selected and ROUTING_PATH.exists():
        errors.append(
            f"Retained contract {ROUTING_PATH} is unsupported without "
            "packaged-cli or mcp-enabled."
        )
    elif routing_selected:
        if not ROUTING_PATH.is_file():
            errors.append(
                f"Selected public-interface profiles require contract file: {ROUTING_PATH}"
            )
        else:
            document = ROUTING_PATH.read_text(encoding="utf-8")
            required_headings = (
                "## Status",
                "## Execution policy",
                "## Contract index",
                "## Cross-interface invariants",
                "## Availability and failure behavior",
                "## Decision rationale",
            )

            for heading in required_headings:
                section = markdown_section(document, heading)
                if section is None or not section.strip():
                    errors.append(
                        f"Selected routing contract {ROUTING_PATH} requires "
                        f"non-empty section '{heading}'."
                    )

            status = field_value(
                markdown_section(document, "## Status"), "Selection status"
            )
            if status != "SELECTED":
                errors.append(
                    f"Selected routing contract {ROUTING_PATH} requires "
                    "'Selection status: SELECTED'."
                )

            if re.search(r"\b(?:TODO|UNSELECTED)\b", document, re.IGNORECASE):
                errors.append(
                    f"Selected routing contract {ROUTING_PATH} must not retain "
                    "TODO or UNSELECTED placeholders."
                )

            cli = (
                Path("CLI_INTERFACE.md").read_text(encoding="utf-8")
                if Path("CLI_INTERFACE.md").is_file()
                else None
            )
            mcp = (
                Path("MCP_INTERFACE.md").read_text(encoding="utf-8")
                if Path("MCP_INTERFACE.md").is_file()
                else None
            )

            cli_launcher_support = (
                support_token(
                    field_value(
                        markdown_section(cli, "## In-place agent launcher"),
                        "Supported",
                    )
                )
                if cli is not None
                else None
            )
            mcp_stdio_support = (
                support_token(
                    field_value(
                        markdown_section(mcp, "## stdio MCP server variant"),
                        "Supported",
                    )
                )
                if mcp is not None
                else None
            )
            mcp_http_support = (
                support_token(
                    field_value(
                        markdown_section(
                            mcp, "## Streamable HTTP MCP server variant"
                        ),
                        "Supported",
                    )
                )
                if mcp is not None
                else None
            )
            mcp_client_support = (
                support_token(
                    field_value(
                        markdown_section(mcp, "## Bundled ad hoc MCP tool client"),
                        "Supported",
                    )
                )
                if mcp is not None
                else None
            )

            canonical_routes = {
                normalize_route(label): label for label in ROUTE_LABELS
            }

            def route_available(canonical: str) -> bool:
                if canonical == "installed human CLI command":
                    return (
                        "packaged-cli" in selected_profiles and cli is not None
                    )
                if canonical == "stable in-place CLI launcher":
                    return (
                        "packaged-cli" in selected_profiles
                        and cli_launcher_support == "YES"
                    )
                if canonical == "native MCP tool already registered in the host":
                    return (
                        "mcp-enabled" in selected_profiles
                        and mcp is not None
                        and "YES" in (mcp_stdio_support, mcp_http_support)
                    )
                if canonical == "existing Streamable HTTP MCP endpoint":
                    return (
                        "mcp-enabled" in selected_profiles
                        and mcp_http_support == "YES"
                    )
                if (
                    canonical
                    == "bundled ad hoc MCP tool client over stdio or Streamable HTTP"
                ):
                    return (
                        "mcp-enabled" in selected_profiles
                        and mcp_client_support == "YES"
                    )
                if canonical == "browser Web interface":
                    return (
                        "browser-interface" in selected_profiles
                        and Path("WEB_INTERFACE.md").is_file()
                    )
                return False

            def validate_route(
                label: str, value: str | None, allow_none: bool
            ) -> str | None:
                if not resolved_value(value):
                    errors.append(
                        f"{ROUTING_PATH} requires a resolved '{label}:' value."
                    )
                    return None

                normalized = normalize_route(value)
                if normalized == "none":
                    if not allow_none:
                        errors.append(
                            f"{ROUTING_PATH} cannot use NONE as the preferred "
                            "agent interface."
                        )
                    return "NONE"

                canonical = canonical_routes.get(normalized)
                if canonical is None:
                    errors.append(
                        f"{ROUTING_PATH} '{label}:' must use one documented "
                        "route category exactly."
                    )
                    return None

                if not route_available(canonical):
                    errors.append(
                        f"{ROUTING_PATH} route '{canonical}' is not implemented "
                        "by the selected profiles and retained contracts."
                    )
                return canonical

            execution = markdown_section(document, "## Execution policy")
            preferred = validate_route(
                "Preferred agent interface",
                field_value(execution, "Preferred agent interface"),
                False,
            )
            fallback_1 = validate_route(
                "Fallback 1", field_value(execution, "Fallback 1"), True
            )
            fallback_2 = validate_route(
                "Fallback 2", field_value(execution, "Fallback 2"), True
            )

            if fallback_1 == "NONE" and fallback_2 and fallback_2 != "NONE":
                errors.append(
                    f"{ROUTING_PATH} cannot define Fallback 2 after "
                    "Fallback 1 is NONE."
                )

            concrete_routes = [
                route
                for route in (preferred, fallback_1, fallback_2)
                if route is not None and route != "NONE"
            ]
            duplicates: list[str] = []
            for route in concrete_routes:
                if concrete_routes.count(route) > 1 and route not in duplicates:
                    duplicates.append(route)
            if duplicates:
                errors.append(
                    f"{ROUTING_PATH} must not repeat a route in the "
                    "preferred/fallback order: "
                    f"{', '.join(duplicates)}."
                )

            availability = markdown_section(
                document, "## Availability and failure behavior"
            )
            for label in (
                "Unavailable preferred interface behavior",
                "Fallback activation conditions",
                "Failure classification exposed to callers",
            ):
                if not concrete_value(field_value(availability, label)):
                    errors.append(
                        f"{ROUTING_PATH} requires a concrete '{label}:' value."
                    )

            rationale = markdown_section(document, "## Decision rationale")
            if not concrete_value(field_value(rationale, "Rationale")):
                errors.append(
                    f"{ROUTING_PATH} requires a concrete 'Rationale:' value."
                )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Public interface routing contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
