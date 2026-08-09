#!/usr/bin/env python3
"""Validate MCP extension selection and first-class MCP Apps contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.profile_contracts import MarkdownDocument, ParseError, ProfileSelection, ValuePolicy


MCP_APPS_EXTENSION = "io.modelcontextprotocol/ui"
MCP_APPS_REVISION = "2026-01-26"
EXTENSION_ID = re.compile(
    r"^[a-z0-9]+(?:\.[a-z0-9-]+)+/[a-z0-9][a-z0-9._-]*$"
)
REQUIRED_APPS_HEADINGS = (
    "## Host capability and fallback",
    "## UI resource inventory",
    "## Tool-to-UI linkage",
    "## Tool visibility and invocation",
    "## Result and presentation data",
    "## View and Host bridge lifecycle",
    "## Sandbox and browser security",
    "## Failure and degradation behavior",
    "## Standalone Web interface boundary",
    "## Required tests",
    "## Decision rationale",
)


def normalize(value: object | None) -> str:
    if value is None:
        return ""
    return ValuePolicy.strip_backticks(value).strip()


def selected_extensions(runtime: MarkdownDocument, errors: list[str]) -> set[str]:
    raw = normalize(runtime.table_value("Optional MCP extensions"))
    if not raw or re.search(r"\b(?:TODO|UNSELECTED)\b", raw, re.IGNORECASE):
        errors.append(
            "RUNTIME.md requires a concrete 'Optional MCP extensions' value for "
            "selected MCP skills."
        )
        return set()

    if raw.upper() == "NONE":
        return set()

    items = {
        normalize(item)
        for item in raw.split(",")
        if normalize(item)
    }
    if not items:
        errors.append(
            "RUNTIME.md Optional MCP extensions must be NONE or a comma-separated "
            "set of extension identifiers."
        )
        return set()
    if any(item.upper() == "NONE" for item in items):
        errors.append(
            "RUNTIME.md Optional MCP extensions cannot combine NONE with extension identifiers."
        )
    for item in sorted(items):
        if not EXTENSION_ID.fullmatch(item):
            errors.append(
                "RUNTIME.md contains an invalid MCP extension identifier: "
                f"{item!r}."
            )
    return items


def apps_implementation_present(root: Path) -> bool:
    directory = root / "mcp" / "apps"
    if directory.is_symlink():
        return True
    if not directory.is_dir():
        return False
    return any(path.is_file() or path.is_symlink() for path in directory.rglob("*"))


def run() -> int:
    root = Path.cwd()
    skill_path = root / "SKILL.md"
    try:
        selection = ProfileSelection.load(skill_path)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if selection.template_scaffold():
        print("MCP extension validation not applicable to the template scaffold.")
        return 0

    profiles = {normalize(profile) for profile in selection.profiles if normalize(profile)}
    apps_contract = root / "MCP_APPS.md"
    apps_files_present = apps_implementation_present(root)

    if "mcp-enabled" not in profiles:
        errors: list[str] = []
        if apps_contract.exists() or apps_contract.is_symlink():
            errors.append(
                "MCP_APPS.md may be retained only by a concrete 'mcp-enabled' Skill "
                "that selects io.modelcontextprotocol/ui."
            )
        if apps_files_present:
            errors.append(
                "mcp/apps implementation files may be retained only when "
                "io.modelcontextprotocol/ui is selected."
            )
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("MCP extension validation not applicable.")
        return 0

    runtime_path = root / "RUNTIME.md"
    if not runtime_path.is_file():
        print(
            "Selected profile 'mcp-enabled' requires RUNTIME.md before MCP extensions can be validated.",
            file=sys.stderr,
        )
        return 1

    errors: list[str] = []
    runtime = MarkdownDocument.read(runtime_path)
    extensions = selected_extensions(runtime, errors)
    extension_selection_valid = not errors
    apps_selected = MCP_APPS_EXTENSION in extensions

    if not extension_selection_valid:
        pass
    elif apps_selected:
        if not apps_contract.is_file() or apps_contract.is_symlink():
            errors.append(
                "Selecting io.modelcontextprotocol/ui requires a regular MCP_APPS.md contract."
            )
        else:
            apps = MarkdownDocument.read(apps_contract)
            if normalize(apps.field("Selection status")) != "SELECTED":
                errors.append(
                    "Selected MCP Apps support requires 'Selection status: SELECTED' in MCP_APPS.md."
                )
            if normalize(apps.field("Extension identifier")) != MCP_APPS_EXTENSION:
                errors.append(
                    "MCP_APPS.md must declare 'Extension identifier: "
                    f"{MCP_APPS_EXTENSION}'."
                )
            if normalize(apps.field("Extension specification revision")) != MCP_APPS_REVISION:
                errors.append(
                    "MCP_APPS.md must select exactly MCP Apps specification revision "
                    f"{MCP_APPS_REVISION}."
                )
            if normalize(apps.field("Core MCP revision")) != "see RUNTIME.md":
                errors.append(
                    "MCP_APPS.md Core MCP revision must be the exact authority pointer "
                    "'see RUNTIME.md'."
                )
            for heading in REQUIRED_APPS_HEADINGS:
                if apps.section(heading) is None:
                    errors.append(
                        f"A selected MCP_APPS.md contract requires section {heading!r}."
                    )
            if re.search(r"\b(?:TODO|UNSELECTED)\b", apps.text, re.IGNORECASE):
                errors.append(
                    "A selected MCP_APPS.md contract must contain no unresolved TODO or UNSELECTED values."
                )
            if "ui/initialize" not in apps.text:
                errors.append(
                    "A selected MCP_APPS.md contract must distinguish the Apps ui/initialize bridge lifecycle."
                )
            if "WEB_INTERFACE.md" not in apps.text or "browser-interface" not in apps.text:
                errors.append(
                    "MCP_APPS.md must document the boundary from the standalone browser-interface contract."
                )
    else:
        if apps_contract.exists() or apps_contract.is_symlink():
            errors.append(
                "A concrete MCP Skill that does not select io.modelcontextprotocol/ui "
                "must remove MCP_APPS.md."
            )
        if apps_files_present:
            errors.append(
                "A concrete MCP Skill that does not select io.modelcontextprotocol/ui "
                "must remove mcp/apps implementation files."
            )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    if apps_selected:
        print("MCP Apps extension contract is valid.")
    else:
        print("MCP extension selection is valid; MCP Apps is not selected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
