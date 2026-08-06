#!/usr/bin/env python3
"""Validate bundled MCP client selections across public and runtime contracts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SKILL_PATH = Path("SKILL.md")
MCP_PATH = Path("MCP_INTERFACE.md")
RUNTIME_PATH = Path("RUNTIME.md")


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


def runtime_reference(value: object | None) -> bool:
    return bool(
        re.fullmatch(
            r"see\s+RUNTIME\.md",
            "" if value is None else str(value).strip(),
            re.IGNORECASE,
        )
    )


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


def transport_category(value: object | None) -> str | None:
    normalized = "" if value is None else str(value).strip().lower()
    return {
        "stdio": "stdio",
        "streamable http": "http",
        "both": "both",
    }.get(normalized)


def ruby_inspect(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def run() -> int:
    if not SKILL_PATH.is_file():
        print(
            f"Missing universally required file: {SKILL_PATH}",
            file=sys.stderr,
        )
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
            f"{SKILL_PATH} must contain exactly one 'Selected profiles:' declaration.",
            file=sys.stderr,
        )
        return 1

    selected_profiles = [
        profile.strip()
        for profile in profile_values[0].split(",")
        if profile.strip()
    ]
    if (
        selected_profiles == ["template-scaffold"]
        or "mcp-enabled" not in selected_profiles
    ):
        print("Bundled MCP client consistency validation is not activated.")
        return 0

    errors: list[str] = []

    if not MCP_PATH.is_file():
        errors.append(f"Selected profile 'mcp-enabled' requires {MCP_PATH}.")
    if not RUNTIME_PATH.is_file():
        errors.append(f"Selected profile 'mcp-enabled' requires {RUNTIME_PATH}.")

    if MCP_PATH.is_file() and RUNTIME_PATH.is_file():
        mcp = MCP_PATH.read_text(encoding="utf-8")
        runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        public_client = markdown_section(
            mcp, "## Bundled ad hoc MCP tool client"
        )
        runtime_client = markdown_section(
            runtime, "### Bundled ad hoc MCP tool client"
        )

        public_support = support_token(
            field_value(public_client, "Supported")
        )
        runtime_support = support_token(
            table_value(runtime_client, "Supported")
        )

        if runtime_support not in {"YES", "NO"}:
            errors.append(
                "Bundled MCP client requires a resolved YES/NO support "
                f"declaration in {RUNTIME_PATH}."
            )

        if (
            public_support in {"YES", "NO"}
            and runtime_support in {"YES", "NO"}
            and public_support != runtime_support
        ):
            errors.append(
                "Bundled MCP client support must agree between "
                f"{MCP_PATH} and {RUNTIME_PATH}."
            )

        if public_support == "YES":
            selection_pairs = (
                ("Scope", "Scope", False),
                (
                    "Negotiation and compatibility behavior",
                    "Negotiation and compatibility behavior",
                    False,
                ),
                ("Invocation scope", "Invocation scope", False),
                ("Interaction modes", "Interaction modes", False),
                (
                    "Task or extension support",
                    "Task or extension support",
                    True,
                ),
            )

            for public_label, runtime_item, allow_not_supported in selection_pairs:
                public_value = field_value(public_client, public_label)
                runtime_value = table_value(runtime_client, runtime_item)
                public_valid = concrete_value(public_value) or bool(
                    allow_not_supported
                    and re.fullmatch(
                        r"NOT\s+SUPPORTED",
                        "" if public_value is None else public_value.strip(),
                        re.IGNORECASE,
                    )
                )
                runtime_valid = concrete_value(runtime_value) or bool(
                    allow_not_supported
                    and re.fullmatch(
                        r"NOT\s+SUPPORTED",
                        "" if runtime_value is None else runtime_value.strip(),
                        re.IGNORECASE,
                    )
                )

                if not public_valid:
                    allowance = (
                        ", 'NOT SUPPORTED'," if allow_not_supported else ""
                    )
                    errors.append(
                        f"Bundled MCP client {public_label} requires a concrete "
                        f"caller-visible value{allowance} or 'see RUNTIME.md'."
                    )
                    continue
                if not runtime_valid:
                    allowance = (
                        " or 'NOT SUPPORTED'" if allow_not_supported else ""
                    )
                    errors.append(
                        f"Bundled MCP client {public_label} requires a concrete "
                        f"authoritative value{allowance} in {RUNTIME_PATH}."
                    )
                    continue
                if runtime_reference(public_value) or public_value == runtime_value:
                    continue

                errors.append(
                    f"Bundled MCP client {public_label} must match "
                    f"{RUNTIME_PATH} exactly or explicitly say 'see RUNTIME.md': "
                    f"{ruby_inspect(public_value)} != "
                    f"{ruby_inspect(runtime_value)}."
                )

            public_transport = field_value(public_client, "Transport used")
            runtime_transport = table_value(
                runtime_client, "Supported transports"
            )
            runtime_category = transport_category(runtime_transport)
            public_category = (
                runtime_category
                if runtime_reference(public_transport)
                else transport_category(public_transport)
            )

            if runtime_category is None:
                errors.append(
                    "Bundled MCP client Supported transports in "
                    f"{RUNTIME_PATH} must be one of: stdio, Streamable HTTP, both."
                )
            if (
                not runtime_reference(public_transport)
                and public_category is None
            ):
                errors.append(
                    "Bundled MCP client Transport used in "
                    f"{MCP_PATH} must be one of: stdio, Streamable HTTP, both, "
                    "or 'see RUNTIME.md'."
                )
            if (
                public_category is not None
                and runtime_category is not None
                and public_category != runtime_category
            ):
                errors.append(
                    "Bundled MCP client Transport used must match "
                    f"{RUNTIME_PATH} exactly or explicitly say 'see RUNTIME.md'."
                )

            required_variants = {
                "stdio": ("stdio",),
                "http": ("http",),
                "both": ("stdio", "http"),
            }.get(runtime_category, ())

            variant_sections = {
                "stdio": (
                    markdown_section(mcp, "## stdio MCP server variant"),
                    markdown_section(runtime, "### stdio variant"),
                ),
                "http": (
                    markdown_section(
                        mcp, "## Streamable HTTP MCP server variant"
                    ),
                    markdown_section(
                        runtime, "### Streamable HTTP variant"
                    ),
                ),
            }

            for variant in required_variants:
                public_variant, runtime_variant = variant_sections[variant]
                public_variant_support = support_token(
                    field_value(public_variant, "Supported")
                )
                runtime_variant_support = support_token(
                    table_value(runtime_variant, "Supported")
                )
                display_name = (
                    "stdio" if variant == "stdio" else "Streamable HTTP"
                )

                if public_variant_support != "YES":
                    errors.append(
                        f"Bundled MCP client transport '{display_name}' requires "
                        f"that variant to set 'Supported: YES' in {MCP_PATH}."
                    )
                if runtime_variant_support != "YES":
                    errors.append(
                        f"Bundled MCP client transport '{display_name}' requires "
                        f"that variant to set 'Supported: YES' in {RUNTIME_PATH}."
                    )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print(
        "Bundled MCP client public, runtime, and transport selections are consistent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
