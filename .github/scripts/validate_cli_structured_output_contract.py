#!/usr/bin/env python3
"""Validate the packaged CLI structured-output contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.profile_contracts import MarkdownDocument, ParseError, ProfileSelection


SKILL_PATH = Path("SKILL.md")
CLI_PATH = Path("CLI_INTERFACE.md")


def run() -> int:
    try:
        selection = ProfileSelection.load(SKILL_PATH)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if selection.template_scaffold() or not selection.selected("packaged-cli"):
        print("CLI structured-output contract is not activated.")
        return 0

    errors: list[str] = []
    if not CLI_PATH.is_file():
        errors.append(
            f"Selected profile 'packaged-cli' requires contract file: {CLI_PATH}"
        )
    else:
        cli = MarkdownDocument.read(CLI_PATH)
        structured = cli.section("### Structured output")

        if structured is None or not structured.strip():
            errors.append(
                f"{CLI_PATH} requires a non-empty '### Structured output' section."
            )
        else:
            structured_document = MarkdownDocument(structured, path=CLI_PATH)
            mode_selector = structured_document.field("Mode selector")
            format_name_value = structured_document.field("Format")
            version_field = structured_document.field("Contract version field")

            unresolved_selector = re.compile(
                r"^(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|FIXME|"
                r"PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|"
                r"SEE\s+DOCUMENTATION)$",
                re.IGNORECASE,
            )
            unresolved_selector_payload = re.compile(
                r"(?:^|[:=]|\s)(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|"
                r"FIXME|PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|"
                r"SEE\s+DOCUMENTATION)(?=$|[\s.,;])",
                re.IGNORECASE,
            )
            option_selector = re.compile(
                r"(?:^|\s)--?[A-Za-z0-9][A-Za-z0-9_-]*"
                r"(?:[=\s]\S+)?(?:\s|$)"
            )
            environment_selector = re.compile(
                r"(?:^|\s)[A-Z][A-Z0-9_]*=\S+(?:\s|$)"
            )
            named_selector = re.compile(
                r"^(?:subcommand|command|option|flag)\s*:\s*\S(?:.*\S)?$",
                re.IGNORECASE,
            )

            selector_is_explicit = bool(
                mode_selector
                and (
                    option_selector.search(mode_selector)
                    or environment_selector.search(mode_selector)
                    or named_selector.fullmatch(mode_selector)
                )
            )
            selector_is_resolved = bool(
                mode_selector
                and not unresolved_selector.fullmatch(mode_selector)
                and not unresolved_selector_payload.search(mode_selector)
            )
            if not selector_is_explicit or not selector_is_resolved:
                errors.append(
                    f"{CLI_PATH} 'Mode selector:' must record an exact, fully "
                    "resolved caller-visible option, subcommand, or environment "
                    "assignment that activates structured output."
                )

            negative_format = re.compile(
                r"\b(?:PLAIN\s+TEXT|HUMAN[-\s]+READABLE|TEXT\s+ONLY|"
                r"NO\s+STRUCTURED|UNSTRUCTURED|"
                r"NOT\s+MACHINE[-\s]+READABLE)\b",
                re.IGNORECASE,
            )
            generic_format = re.compile(
                r"^(?:TEXT|BINARY|CUSTOM|OTHER|UNKNOWN|NONE|"
                r"NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|UNSELECTED)$",
                re.IGNORECASE,
            )
            explicit_format_name = re.compile(
                r"^(?=.{1,80}$)(?:[A-Za-z0-9][A-Za-z0-9._+/-]*)"
                r"(?:[ -][A-Za-z0-9][A-Za-z0-9._+/-]*){0,5}$"
            )
            if not (
                format_name_value
                and explicit_format_name.fullmatch(format_name_value)
                and not negative_format.search(format_name_value)
                and not generic_format.fullmatch(format_name_value)
            ):
                errors.append(
                    f"{CLI_PATH} 'Format:' must name an explicit machine-readable "
                    "structured serialization format."
                )

            negative_version = re.compile(
                r"^(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|"
                r"NO\s+VERSION\s+FIELD)$|"
                r"\b(?:WITHOUT|OMITTED|ABSENT)\b",
                re.IGNORECASE,
            )
            field_selector = re.compile(
                r"^(?:[A-Za-z_$][A-Za-z0-9_$-]*"
                r"(?:\.[A-Za-z_$][A-Za-z0-9_$-]*)*|"
                r"/(?:[^/\s]+/)*[^/\s]+)$"
            )
            if not (
                version_field
                and not negative_version.search(version_field)
                and field_selector.fullmatch(version_field)
            ):
                errors.append(
                    f"{CLI_PATH} 'Contract version field:' must name one concrete "
                    "field or field path."
                )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("CLI structured-output contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
