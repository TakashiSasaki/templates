#!/usr/bin/env python3
"""Validate the MCP runtime-authority declaration."""

from __future__ import annotations

import sys
from pathlib import Path

from lib.profile_contracts import MarkdownDocument, ParseError, ProfileSelection


SKILL_PATH = Path("SKILL.md")
MCP_PATH = Path("MCP_INTERFACE.md")
AUTHORITY_LABEL = "Runtime, SDK, revision, era boundary, and schema source of truth"


def run() -> int:
    if not SKILL_PATH.is_file():
        print(f"Missing universally required file: {SKILL_PATH}", file=sys.stderr)
        return 1

    try:
        selection = ProfileSelection.load(SKILL_PATH)
    except ParseError as exc:
        print(exc, file=sys.stderr)
        return 1

    if selection.template_scaffold() or not selection.selected("mcp-enabled"):
        print("MCP runtime-authority declaration is not activated.")
        return 0

    errors: list[str] = []
    if not MCP_PATH.is_file():
        errors.append(
            f"Selected profile 'mcp-enabled' requires contract file: {MCP_PATH}"
        )
    else:
        mcp = MarkdownDocument.read(MCP_PATH)
        protocol = mcp.section("## MCP protocol reference")
        values: list[str] = []
        if protocol is not None:
            protocol_document = MarkdownDocument(protocol, path=MCP_PATH)
            for raw_line in protocol_document.lines:
                value = protocol_document.field(AUTHORITY_LABEL, section=raw_line)
                if value is not None:
                    values.append(value)

        if len(values) != 1:
            errors.append(
                f"{MCP_PATH} must contain exactly one '{AUTHORITY_LABEL}:' "
                "declaration under '## MCP protocol reference'."
            )
        elif values[0] != "RUNTIME.md":
            errors.append(
                f"{MCP_PATH} '{AUTHORITY_LABEL}:' must resolve exactly to RUNTIME.md."
            )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("MCP runtime-authority declaration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
