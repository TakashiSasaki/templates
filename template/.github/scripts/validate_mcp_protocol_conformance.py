#!/usr/bin/env python3
"""Validate the unpublished template's MCP 2026-07-28 Modern baseline."""

from __future__ import annotations

import re
import sys
from pathlib import Path


BASELINE_REVISION = "2026-07-28"


def selected_profiles(skill_text: str) -> set[str]:
    match = re.search(r"^Selected profiles:\s*(.+?)\s*$", skill_text, re.MULTILINE)
    if not match:
        return set()
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


def table_value(markdown: str, label: str) -> str | None:
    pattern = re.compile(
        rf"^\|\s*{re.escape(label)}\s*\|\s*(.*?)\s*\|\s*$",
        re.MULTILINE,
    )
    match = pattern.search(markdown)
    return match.group(1).strip() if match else None


def normalized(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("`", "").strip()


def unresolved(value: str | None) -> bool:
    text = normalized(value)
    return not text or bool(re.search(r"\b(?:TODO|UNSELECTED)\b", text, re.IGNORECASE))


def section(markdown: str, heading: str) -> str:
    match = re.search(
        rf"^{re.escape(heading)}\s*$([\s\S]*?)(?=^##?\s|\Z)",
        markdown,
        re.MULTILINE,
    )
    return match.group(1) if match else ""


def run() -> int:
    root = Path.cwd()
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        print("Missing SKILL.md.", file=sys.stderr)
        return 1

    profiles = selected_profiles(skill_path.read_text(encoding="utf-8"))
    if "template-scaffold" in profiles or "mcp-enabled" not in profiles:
        print("MCP 2026-07-28 baseline validation not applicable.")
        return 0

    runtime_path = root / "RUNTIME.md"
    interface_path = root / "MCP_INTERFACE.md"
    if not runtime_path.is_file() or not interface_path.is_file():
        print(
            "Selected profile 'mcp-enabled' requires RUNTIME.md and MCP_INTERFACE.md.",
            file=sys.stderr,
        )
        return 1

    runtime = runtime_path.read_text(encoding="utf-8")
    interface = interface_path.read_text(encoding="utf-8")
    errors: list[str] = []

    revisions = normalized(table_value(runtime, "Supported protocol revisions"))
    if revisions != BASELINE_REVISION:
        errors.append(
            "RUNTIME.md must select exactly MCP protocol revision 2026-07-28; "
            f"got {revisions!r}."
        )

    eras = normalized(table_value(runtime, "Supported protocol eras")).lower()
    if eras != "modern":
        errors.append(
            "RUNTIME.md must select exactly the Modern protocol era for the "
            "2026-07-28 baseline."
        )

    negotiation = normalized(table_value(runtime, "Default revision or negotiation mode"))
    if unresolved(negotiation) or BASELINE_REVISION not in negotiation:
        errors.append(
            "RUNTIME.md must state a concrete 2026-07-28-only negotiation or pinning policy."
        )
    if re.search(r"\b(?:auto|fallback|fall back|dual|legacy)\b", negotiation, re.IGNORECASE):
        errors.append(
            "RUNTIME.md must not select automatic legacy fallback for the unpublished "
            "Modern-only baseline."
        )

    legacy_policy = normalized(table_value(runtime, "Legacy compatibility policy"))
    if not re.search(r"\bNOT SUPPORTED\b", legacy_policy, re.IGNORECASE):
        errors.append(
            "RUNTIME.md Legacy compatibility policy must explicitly be NOT SUPPORTED."
        )

    deprecated_policy = normalized(table_value(runtime, "Deprecated feature policy"))
    if unresolved(deprecated_policy):
        errors.append("RUNTIME.md requires a concrete deprecated-feature policy.")
    elif not re.search(r"\b(?:not advertised|not supported|excluded|disabled)\b", deprecated_policy, re.IGNORECASE):
        errors.append(
            "RUNTIME.md deprecated-feature policy must explicitly exclude deprecated "
            "features from the initial template baseline."
        )

    for required_phrase in (
        "server/discover",
        "UnsupportedProtocolVersionError",
        "per-request",
    ):
        if required_phrase.lower() not in interface.lower():
            errors.append(
                f"MCP_INTERFACE.md must describe Modern baseline behavior for {required_phrase}."
            )

    if re.search(r"\bsend\s+`?initialize`?", interface, re.IGNORECASE):
        errors.append(
            "MCP_INTERFACE.md must not instruct callers to send the Legacy initialize handshake."
        )
    if "notifications/initialized" in interface:
        errors.append(
            "MCP_INTERFACE.md must not require the Legacy notifications/initialized message."
        )

    stdio = section(runtime, "### stdio variant")
    if normalized(table_value(stdio, "Supported")) == "YES":
        discovery = normalized(table_value(stdio, "Protocol negotiation/discovery"))
        if "server/discover" not in discovery or BASELINE_REVISION not in discovery:
            errors.append(
                "A supported stdio variant must use server/discover and the 2026-07-28 "
                "Modern revision without Legacy fallback."
            )

    http = section(runtime, "### Streamable HTTP variant")
    if normalized(table_value(http, "Supported")) == "YES":
        http_eras = normalized(table_value(http, "Supported protocol eras")).lower()
        if http_eras != "modern":
            errors.append("A supported Streamable HTTP variant must be Modern-only.")
        state_model = normalized(table_value(http, "Revision-specific state model"))
        if not re.search(r"\b(?:stateless|no protocol sessions|request-scoped)\b", state_model, re.IGNORECASE):
            errors.append(
                "Modern Streamable HTTP must explicitly avoid protocol-level sessions."
            )
        removed = normalized(
            table_value(http, "`Mcp-Session-Id`, GET, DELETE, and resumability")
        )
        if not re.search(r"\bNOT USED\b", removed, re.IGNORECASE):
            errors.append(
                "Modern Streamable HTTP must mark Mcp-Session-Id, GET, DELETE, and "
                "resumability NOT USED."
            )
        fallback = normalized(
            table_value(http, "Initialization-era fallback on the same endpoint")
        )
        if not re.search(r"\bNOT SUPPORTED\b", fallback, re.IGNORECASE):
            errors.append(
                "Modern Streamable HTTP must mark initialization-era fallback NOT SUPPORTED."
            )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("MCP 2026-07-28 Modern baseline contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
