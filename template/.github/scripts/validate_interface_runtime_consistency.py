#!/usr/bin/env python3
"""Validate consistency between public interface and runtime contracts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SKILL_PATH = Path("SKILL.md")
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


def ruby_inspect(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def run() -> int:
    if not SKILL_PATH.is_file():
        print("Missing universally required file: SKILL.md", file=sys.stderr)
        return 1

    skill_lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
    profile_values: list[str] = []
    for raw_line in skill_lines:
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
            "Public interface and runtime contracts are consistent for the "
            "template scaffold."
        )
        return 0

    checked_profiles = set(selected_profiles) & {"packaged-cli", "mcp-enabled"}
    if not checked_profiles:
        print("No packaged CLI or MCP consistency checks are activated.")
        return 0

    errors: list[str] = []

    if not RUNTIME_PATH.is_file():
        errors.append(
            f"Selected public-interface profiles require runtime authority: {RUNTIME_PATH}"
        )

    runtime = (
        RUNTIME_PATH.read_text(encoding="utf-8")
        if RUNTIME_PATH.is_file()
        else None
    )

    def compare_commands(
        label: str,
        public_value: str | None,
        authoritative_value: str | None,
        authority: Path,
    ) -> None:
        if not concrete_value(public_value):
            errors.append(f"{label} requires a concrete caller-visible command.")
            return
        if not concrete_value(authoritative_value):
            errors.append(
                f"{label} requires a concrete matching command in {authority}."
            )
            return
        if public_value == authoritative_value:
            return

        errors.append(
            f"{label} must match {authority} exactly: "
            f"{ruby_inspect(public_value)} != {ruby_inspect(authoritative_value)}."
        )

    def compare_selections(
        label: str,
        public_value: str | None,
        runtime_value: str | None,
    ) -> None:
        if not concrete_value(public_value):
            errors.append(
                f"{label} requires a concrete caller-visible value or 'see RUNTIME.md'."
            )
            return
        if not concrete_value(runtime_value):
            errors.append(
                f"{label} requires a concrete authoritative value in {RUNTIME_PATH}."
            )
            return
        if runtime_reference(public_value) or public_value == runtime_value:
            return

        errors.append(
            f"{label} must match {RUNTIME_PATH} exactly or explicitly say "
            f"'see RUNTIME.md': {ruby_inspect(public_value)} != "
            f"{ruby_inspect(runtime_value)}."
        )

    if "packaged-cli" in selected_profiles and runtime is not None:
        cli_path = Path("CLI_INTERFACE.md")
        if cli_path.is_file():
            cli = cli_path.read_text(encoding="utf-8")
            public_command = field_value(
                markdown_section(cli, "## Human CLI"), "Command"
            )
            runtime_command = table_value(
                markdown_section(runtime, "### Packaged CLI commands"),
                "Human CLI",
            )
            compare_commands(
                "Packaged CLI command",
                public_command,
                runtime_command,
                RUNTIME_PATH,
            )

            canonical_values: list[str] = []
            for raw_line in skill_lines:
                normalized = raw_line.strip()
                if normalized.startswith("- "):
                    normalized = normalized[2:].strip()
                match = re.fullmatch(
                    r"Canonical command:\s*(.+?)\s*", normalized
                )
                if match:
                    canonical_values.append(strip_backticks(match.group(1)))

            if len(canonical_values) != 1:
                errors.append(
                    "Selected profile 'packaged-cli' requires exactly one "
                    "'Canonical command:' summary in SKILL.md."
                )
            else:
                compare_commands(
                    "Packaged CLI command",
                    public_command,
                    canonical_values[0],
                    SKILL_PATH,
                )

            launcher = markdown_section(cli, "## In-place agent launcher")
            if support_token(field_value(launcher, "Supported")) == "YES":
                public_launcher = field_value(launcher, "Command")
                runtime_launcher = table_value(
                    markdown_section(runtime, "### Shared development commands"),
                    "Agent launcher",
                )
                compare_commands(
                    "In-place CLI launcher command",
                    public_launcher,
                    runtime_launcher,
                    RUNTIME_PATH,
                )
        else:
            errors.append(
                "Selected profile 'packaged-cli' requires CLI_INTERFACE.md "
                "for consistency validation."
            )

    if "mcp-enabled" in selected_profiles and runtime is not None:
        mcp_path = Path("MCP_INTERFACE.md")
        if not mcp_path.is_file():
            errors.append(
                "Selected profile 'mcp-enabled' requires MCP_INTERFACE.md "
                "for consistency validation."
            )
        else:
            mcp = mcp_path.read_text(encoding="utf-8")
            runtime_commands = markdown_section(runtime, "### MCP commands")

            variant_specs = (
                {
                    "name": "stdio MCP server",
                    "public_heading": "## stdio MCP server variant",
                    "runtime_heading": "### stdio variant",
                    "command_pairs": (("Launch command", "Start stdio MCP server"),),
                    "selection_pairs": (("Lifecycle owner", "Lifecycle owner"),),
                },
                {
                    "name": "Streamable HTTP MCP server",
                    "public_heading": "## Streamable HTTP MCP server variant",
                    "runtime_heading": "### Streamable HTTP variant",
                    "command_pairs": (
                        ("Start command", "Start Streamable HTTP MCP server"),
                        (
                            "Stop command or shutdown method",
                            "Stop Streamable HTTP MCP server",
                        ),
                        ("Health/readiness check", "Check MCP readiness"),
                    ),
                    "selection_pairs": (
                        ("Bind address", "Default bind address"),
                        ("Port selection", "Port"),
                        ("Supported protocol eras", "Supported protocol eras"),
                        (
                            "Revision-specific state model",
                            "Revision-specific state model",
                        ),
                        ("Authentication", "Authentication"),
                    ),
                },
            )

            for specification in variant_specs:
                public_section = markdown_section(
                    mcp, specification["public_heading"]
                )
                runtime_section = markdown_section(
                    runtime, specification["runtime_heading"]
                )
                public_support = support_token(
                    field_value(public_section, "Supported")
                )
                runtime_support = support_token(
                    table_value(runtime_section, "Supported")
                )
                name = specification["name"]

                if runtime_support not in {"YES", "NO"}:
                    errors.append(
                        f"{name} requires a resolved YES/NO support declaration "
                        f"in {RUNTIME_PATH}."
                    )

                if (
                    public_support in {"YES", "NO"}
                    and runtime_support in {"YES", "NO"}
                    and public_support != runtime_support
                ):
                    errors.append(
                        f"{name} support must agree between MCP_INTERFACE.md "
                        f"and {RUNTIME_PATH}."
                    )

                if public_support != "YES":
                    continue

                for public_label, runtime_purpose in specification["command_pairs"]:
                    compare_commands(
                        f"{name} {public_label}",
                        field_value(public_section, public_label),
                        table_value(runtime_commands, runtime_purpose),
                        RUNTIME_PATH,
                    )

                for public_label, runtime_item in specification["selection_pairs"]:
                    compare_selections(
                        f"{name} {public_label}",
                        field_value(public_section, public_label),
                        table_value(runtime_section, runtime_item),
                    )

            public_client = markdown_section(
                mcp, "## Bundled ad hoc MCP tool client"
            )
            runtime_client = markdown_section(
                runtime, "### Bundled ad hoc MCP tool client"
            )
            public_client_support = support_token(
                field_value(public_client, "Supported")
            )
            runtime_client_support = support_token(
                table_value(runtime_client, "Supported")
            )

            if runtime_client_support not in {"YES", "NO"}:
                errors.append(
                    "Bundled MCP client requires a resolved YES/NO support "
                    f"declaration in {RUNTIME_PATH}."
                )

            if (
                public_client_support in {"YES", "NO"}
                and runtime_client_support in {"YES", "NO"}
                and public_client_support != runtime_client_support
            ):
                errors.append(
                    "Bundled MCP client support must agree between "
                    f"MCP_INTERFACE.md and {RUNTIME_PATH}."
                )

            stable_public_command = table_value(
                runtime_client, "Stable public command"
            )
            if not resolved_value(stable_public_command):
                errors.append(
                    "Bundled MCP client Stable public command requires an "
                    f"explicit value in {RUNTIME_PATH}."
                )
            elif public_client_support == "NO" or runtime_client_support == "NO":
                if not re.fullmatch(
                    r"NOT\s+SUPPORTED",
                    stable_public_command.strip(),
                    re.IGNORECASE,
                ):
                    errors.append(
                        "Bundled MCP client Stable public command must be "
                        "'NOT SUPPORTED' when the bundled client is disabled."
                    )
            elif (
                concrete_value(stable_public_command)
                and "packaged-cli" not in selected_profiles
            ):
                errors.append(
                    "Bundled MCP client Stable public command requires the "
                    "'packaged-cli' profile."
                )

            if public_client_support == "YES":
                compare_commands(
                    "Bundled MCP client command",
                    field_value(public_client, "Command"),
                    table_value(runtime_client, "Bundled helper command"),
                    RUNTIME_PATH,
                )
                compare_selections(
                    "Bundled MCP client transport",
                    field_value(public_client, "Transport used"),
                    table_value(runtime_client, "Supported transports"),
                )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Public interface and runtime contracts are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
