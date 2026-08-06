#!/usr/bin/env python3
"""Reject unresolved scalar placeholders in selected concrete contracts."""

from __future__ import annotations

import sys
from pathlib import Path

from lib.profile_contracts import MarkdownDocument, ParseError, ProfileSelection, ValuePolicy


SKILL_PATH = Path("SKILL.md")
ROUTING_PATH = Path("INTERFACES.md")
RUNTIME_PATH = Path("RUNTIME.md")
WEB_PATH = Path("WEB_INTERFACE.md")
RUNTIME_REQUIRED_PROFILES = {
    "packaged-cli",
    "mcp-enabled",
    "browser-interface",
    "headless-service",
}


def run() -> int:
    try:
        selection = ProfileSelection.load(SKILL_PATH)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if selection.template_scaffold():
        print(
            "Selected-contract scalar placeholder validation is not activated "
            "for the template scaffold."
        )
        return 0

    errors: list[str] = []

    def scan_scalar_values(
        path: Path,
        document: MarkdownDocument,
        context: str | None = None,
        line_offset: int = 0,
    ) -> None:
        for entry in document.each_scalar():
            if not ValuePolicy.unresolved_scalar(entry.value):
                continue

            location = f"{path}:{line_offset + entry.line_number}"
            if context:
                location += f" ({context})"
            value = ValuePolicy.strip_backticks(entry.value)
            rendered = repr(value)

            if entry.kind == "field":
                errors.append(
                    f"{location} '{entry.label}:' must not use unresolved "
                    f"scalar placeholder {rendered}."
                )
            elif entry.kind == "table":
                errors.append(
                    f"{location} table value must not use unresolved "
                    f"scalar placeholder {rendered}."
                )
            else:
                errors.append(
                    f"{location} must not contain standalone unresolved "
                    f"scalar placeholder {rendered}."
                )

    skill_document = MarkdownDocument.read(SKILL_PATH)
    selected_profiles = set(selection.profiles)

    scan_scalar_values(SKILL_PATH, skill_document)

    routing_selected = bool(
        selected_profiles.intersection({"packaged-cli", "mcp-enabled"})
    )
    runtime_required = bool(
        selected_profiles.intersection(RUNTIME_REQUIRED_PROFILES)
    )
    runtime_retained = runtime_required or (
        selection.selected("script-assisted") and RUNTIME_PATH.is_file()
    )

    if runtime_retained:
        for label in ("Canonical command", "Working directory"):
            for value in skill_document.summary_values(label):
                if ValuePolicy.unresolved_scalar(value):
                    errors.append(
                        f"{SKILL_PATH} '{label}:' must not use unresolved "
                        f"scalar placeholder {value!r}."
                    )

    if routing_selected:
        for label in ("Preferred agent route", "Detailed interface contract"):
            for value in skill_document.summary_values(label):
                if ValuePolicy.unresolved_scalar(value):
                    errors.append(
                        f"{SKILL_PATH} '{label}:' must not use unresolved "
                        f"scalar placeholder {value!r}."
                    )

    selected_contracts: list[Path] = []
    if routing_selected:
        selected_contracts.append(ROUTING_PATH)
    if selection.selected("packaged-cli"):
        selected_contracts.append(Path("CLI_INTERFACE.md"))
    if selection.selected("mcp-enabled"):
        selected_contracts.append(Path("MCP_INTERFACE.md"))
    if selection.selected("browser-interface"):
        selected_contracts.append(WEB_PATH)

    for path in selected_contracts:
        if not path.is_file():
            errors.append(f"Selected profile requires contract file: {path}")
            continue
        scan_scalar_values(path, MarkdownDocument.read(path))

    if runtime_required and not RUNTIME_PATH.is_file():
        errors.append(
            f"Selected runtime-backed profile requires contract file: {RUNTIME_PATH}"
        )
    elif runtime_retained:
        runtime = MarkdownDocument.read(RUNTIME_PATH)
        runtime_headings = [
            "## Status",
            "## Primary implementation",
            "### Shared development commands",
            "## Distribution",
            "## Environment and configuration",
            "## Decision rationale",
        ]
        if selection.selected("packaged-cli"):
            runtime_headings.append("### Packaged CLI commands")
        if selection.selected("mcp-enabled"):
            runtime_headings.extend(
                [
                    "### MCP commands",
                    "## MCP protocol support",
                    "### stdio variant",
                    "### Streamable HTTP variant",
                    "### Bundled ad hoc MCP tool client",
                ]
            )
        if selection.selected("browser-interface"):
            runtime_headings.extend(
                [
                    "### Browser-interface commands",
                    "## Optional human verification Web interface deployment",
                ]
            )
        if selection.selected("headless-service"):
            runtime_headings.extend(
                [
                    "### Headless-service commands",
                    "## Headless service deployment",
                ]
            )

        for heading in dict.fromkeys(runtime_headings):
            section = runtime.section(heading)
            if section is None:
                continue
            heading_line_number = next(
                (
                    index
                    for index, line in enumerate(runtime.lines, start=1)
                    if line.rstrip() == heading
                ),
                0,
            )
            scan_scalar_values(
                RUNTIME_PATH,
                MarkdownDocument(section, path=RUNTIME_PATH),
                heading,
                line_offset=heading_line_number,
            )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print(
        "Concrete SKILL, selected routing/interface, and runtime scalar values "
        "contain no unresolved placeholders."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
