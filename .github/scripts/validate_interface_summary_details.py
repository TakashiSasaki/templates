#!/usr/bin/env python3
"""Validate caller-facing interface summaries and endpoint details."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


SKILL_PATH = Path("SKILL.md")
CLI_PATH = Path("CLI_INTERFACE.md")
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


def fully_concrete_value(value: str | None) -> bool:
    return bool(
        resolved_value(value)
        and not re.search(
            r"\b(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))\b",
            value,
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


def summary_values(lines: list[str], label: str) -> list[str]:
    values: list[str] = []
    for raw_line in lines:
        normalized = raw_line.strip()
        if normalized.startswith("- "):
            normalized = normalized[2:].strip()
        match = re.fullmatch(rf"{re.escape(label)}:\s*(.+?)\s*", normalized)
        if match:
            values.append(strip_backticks(match.group(1)))
    return values


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

    skill_lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
    profile_values = summary_values(skill_lines, "Selected profiles")
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
    if selected_profiles == ["template-scaffold"]:
        print("Interface summary details are valid for the template scaffold.")
        return 0

    errors: list[str] = []
    public_profiles = set(selected_profiles) & {"packaged-cli", "mcp-enabled"}

    if public_profiles:
        route_summaries = summary_values(skill_lines, "Preferred agent route")
        if len(route_summaries) != 1:
            errors.append(
                "Selected public-interface profiles require exactly one "
                f"'Preferred agent route:' summary in {SKILL_PATH}."
            )
        elif not fully_concrete_value(route_summaries[0]):
            errors.append(
                f"{SKILL_PATH} requires a concrete 'Preferred agent route:' summary."
            )
        elif route_summaries[0] != "see INTERFACES.md":
            errors.append(
                "Preferred agent route must be 'see INTERFACES.md' for selected "
                "public-interface profiles."
            )

        contract_summaries = summary_values(
            skill_lines, "Detailed interface contract"
        )
        expected_contracts: list[Path] = []
        if "packaged-cli" in selected_profiles:
            expected_contracts.append(CLI_PATH)
        if "mcp-enabled" in selected_profiles:
            expected_contracts.append(MCP_PATH)
        expected_contract_summary = " and ".join(map(str, expected_contracts))

        if len(contract_summaries) != 1:
            errors.append(
                "Selected public-interface profiles require exactly one "
                f"'Detailed interface contract:' summary in {SKILL_PATH}."
            )
        elif not fully_concrete_value(contract_summaries[0]):
            errors.append(
                f"{SKILL_PATH} requires a concrete "
                "'Detailed interface contract:' summary."
            )
        elif contract_summaries[0] != expected_contract_summary:
            errors.append(
                "Detailed interface contract must reference exactly the selected "
                "caller contracts: "
                f"expected {ruby_inspect(expected_contract_summary)}, got "
                f"{ruby_inspect(contract_summaries[0])}."
            )

    if "packaged-cli" in selected_profiles:
        if not CLI_PATH.is_file():
            errors.append(f"Selected profile 'packaged-cli' requires {CLI_PATH}.")
        else:
            cli = CLI_PATH.read_text(encoding="utf-8")
            cli_working_directory = field_value(
                markdown_section(cli, "## Human CLI"),
                "Working directory",
            )
            skill_working_directories = summary_values(
                skill_lines, "Working directory"
            )

            if len(skill_working_directories) != 1:
                errors.append(
                    "Selected profile 'packaged-cli' requires exactly one "
                    f"'Working directory:' summary in {SKILL_PATH}."
                )
            elif not concrete_value(skill_working_directories[0]):
                errors.append(
                    f"{SKILL_PATH} requires a concrete packaged-CLI "
                    "'Working directory:' summary."
                )
            elif not concrete_value(cli_working_directory):
                errors.append(
                    f"{CLI_PATH} requires a concrete packaged-CLI "
                    "'Working directory:' value."
                )
            elif skill_working_directories[0] != cli_working_directory:
                errors.append(
                    "Packaged CLI working directory must match between "
                    f"{SKILL_PATH} and {CLI_PATH}: "
                    f"{ruby_inspect(skill_working_directories[0])} != "
                    f"{ruby_inspect(cli_working_directory)}."
                )

    if "mcp-enabled" in selected_profiles:
        if not MCP_PATH.is_file():
            errors.append(f"Selected profile 'mcp-enabled' requires {MCP_PATH}.")
        if not RUNTIME_PATH.is_file():
            errors.append(f"Selected profile 'mcp-enabled' requires {RUNTIME_PATH}.")

        if MCP_PATH.is_file() and RUNTIME_PATH.is_file():
            mcp = MCP_PATH.read_text(encoding="utf-8")
            runtime = RUNTIME_PATH.read_text(encoding="utf-8")
            public_http = markdown_section(
                mcp, "## Streamable HTTP MCP server variant"
            )
            runtime_http = markdown_section(
                runtime, "### Streamable HTTP variant"
            )

            if support_token(field_value(public_http, "Supported")) == "YES":
                endpoint = field_value(public_http, "Endpoint URL")

                if not concrete_value(endpoint):
                    errors.append(
                        "Supported Streamable HTTP requires a concrete "
                        "'Endpoint URL:' or 'see RUNTIME.md'."
                    )
                elif not runtime_reference(endpoint):
                    runtime_bind = table_value(
                        runtime_http, "Default bind address"
                    )
                    runtime_port = table_value(runtime_http, "Port")
                    runtime_path = table_value(runtime_http, "Endpoint path")

                    for label, value in (
                        ("Default bind address", runtime_bind),
                        ("Port", runtime_port),
                        ("Endpoint path", runtime_path),
                    ):
                        if not concrete_value(value):
                            errors.append(
                                "Concrete Streamable HTTP Endpoint URL requires a "
                                f"concrete '{label}' in {RUNTIME_PATH}; otherwise "
                                "use 'Endpoint URL: see RUNTIME.md'."
                            )

                    if (
                        concrete_value(runtime_bind)
                        and concrete_value(runtime_port)
                        and concrete_value(runtime_path)
                    ):
                        if not re.fullmatch(r"\d+", runtime_port) or not (
                            1 <= int(runtime_port) <= 65_535
                        ):
                            errors.append(
                                "Concrete Streamable HTTP Endpoint URL requires a "
                                "fixed numeric runtime port; otherwise use "
                                "'Endpoint URL: see RUNTIME.md'."
                            )
                        else:
                            try:
                                uri = urlsplit(endpoint)
                                parsed_port = uri.port
                            except ValueError:
                                errors.append(
                                    "Streamable HTTP Endpoint URL is not a valid URI: "
                                    f"{ruby_inspect(endpoint)}."
                                )
                            else:
                                if (
                                    uri.scheme not in {"http", "https"}
                                    or not uri.hostname
                                ):
                                    errors.append(
                                        "Streamable HTTP Endpoint URL must be an "
                                        "absolute http or https URL."
                                    )
                                else:
                                    if uri.username is not None or uri.password is not None:
                                        errors.append(
                                            "Streamable HTTP Endpoint URL must not "
                                            "embed credentials or other userinfo."
                                        )

                                    public_host = uri.hostname
                                    authoritative_host = re.sub(
                                        r"^\[(.*)\]$",
                                        r"\1",
                                        runtime_bind,
                                    )
                                    wildcard_bind = authoritative_host in {
                                        "0.0.0.0",
                                        "::",
                                    }

                                    if (
                                        not wildcard_bind
                                        and public_host != authoritative_host
                                    ):
                                        errors.append(
                                            "Streamable HTTP Endpoint URL host must "
                                            f"match {RUNTIME_PATH}: "
                                            f"{ruby_inspect(public_host)} != "
                                            f"{ruby_inspect(authoritative_host)}."
                                        )

                                    effective_port = parsed_port
                                    if effective_port is None:
                                        effective_port = (
                                            80 if uri.scheme == "http" else 443
                                        )
                                    if effective_port != int(runtime_port):
                                        errors.append(
                                            "Streamable HTTP Endpoint URL port must "
                                            f"match {RUNTIME_PATH}: "
                                            f"{ruby_inspect(effective_port)} != "
                                            f"{ruby_inspect(int(runtime_port))}."
                                        )
                                    if uri.path != runtime_path:
                                        errors.append(
                                            "Streamable HTTP Endpoint URL path must "
                                            f"match {RUNTIME_PATH}: "
                                            f"{ruby_inspect(uri.path)} != "
                                            f"{ruby_inspect(runtime_path)}."
                                        )
                                    if uri.query or uri.fragment:
                                        errors.append(
                                            "Streamable HTTP Endpoint URL must not "
                                            "add a query or fragment to the runtime "
                                            "endpoint path."
                                        )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Interface summary details are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
