#!/usr/bin/env python3
"""Validate MCP extension selection and first-class MCP Apps contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path


MCP_APPS_EXTENSION = "io.modelcontextprotocol/ui"
MCP_APPS_REVISION = "2026-01-26"
EXTENSION_ID = re.compile(
    r"^[a-z0-9]+(?:\.[a-z0-9-]+)+/[a-z0-9][a-z0-9._-]*$"
)


def selected_profiles(skill_text: str) -> set[str]:
    match = re.search(r"^Selected profiles:\s*(.+?)\s*$", skill_text, re.MULTILINE)
    if not match:
        return set()
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


def table_value(markdown: str, label: str) -> str | None:
    match = re.search(
        rf"^\|\s*{re.escape(label)}\s*\|\s*(.*?)\s*\|\s*$",
        markdown,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def scalar(markdown: str, label: str) -> str | None:
    match = re.search(
        rf"^{re.escape(label)}:\s*(.*?)\s*$",
        markdown,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def normalize(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("`", "").strip()


def selected_extensions(runtime: str, errors: list[str]) -> set[str]:
    raw = normalize(table_value(runtime, "Optional MCP extensions"))
    if not raw or re.search(r"\b(?:TODO|UNSELECTED)\b", raw, re.IGNORECASE):
        errors.append(
            "RUNTIME.md requires a concrete 'Optional MCP extensions' value for "
            "selected MCP skills."
        )
        return set()

    if raw.upper() == "NONE":
        return set()

    items = {item.strip() for item in raw.split(",") if item.strip()}
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
    if not skill_path.is_file():
        print("Missing SKILL.md.", file=sys.stderr)
        return 1

    profiles = selected_profiles(skill_path.read_text(encoding="utf-8"))
    if "template-scaffold" in profiles:
        print("MCP extension validation not applicable to the template scaffold.")
        return 0

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
    runtime = runtime_path.read_text(encoding="utf-8")
    extensions = selected_extensions(runtime, errors)
    apps_selected = MCP_APPS_EXTENSION in extensions

    if apps_selected:
        if not apps_contract.is_file() or apps_contract.is_symlink():
            errors.append(
                "Selecting io.modelcontextprotocol/ui requires a regular MCP_APPS.md contract."
            )
        else:
            apps = apps_contract.read_text(encoding="utf-8")
            if normalize(scalar(apps, "Selection status")) != "SELECTED":
                errors.append(
                    "Selected MCP Apps support requires 'Selection status: SELECTED' in MCP_APPS.md."
                )
            if normalize(scalar(apps, "Extension identifier")) != MCP_APPS_EXTENSION:
                errors.append(
                    "MCP_APPS.md must declare 'Extension identifier: "
                    f"{MCP_APPS_EXTENSION}'."
                )
            if normalize(scalar(apps, "Extension specification revision")) != MCP_APPS_REVISION:
                errors.append(
                    "MCP_APPS.md must select exactly MCP Apps specification revision "
                    f"{MCP_APPS_REVISION}."
                )
            if normalize(scalar(apps, "Core MCP revision")) != "see RUNTIME.md":
                errors.append(
                    "MCP_APPS.md Core MCP revision must be the exact authority pointer "
                    "'see RUNTIME.md'."
                )
            if re.search(r"\b(?:TODO|UNSELECTED)\b", apps, re.IGNORECASE):
                errors.append(
                    "A selected MCP_APPS.md contract must contain no unresolved TODO or UNSELECTED values."
                )
            if "ui/initialize" not in apps:
                errors.append(
                    "A selected MCP_APPS.md contract must distinguish the Apps ui/initialize bridge lifecycle."
                )
            if "WEB_INTERFACE.md" not in apps or "browser-interface" not in apps:
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
