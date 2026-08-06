#!/usr/bin/env python3
"""Validate the packaged CLI exit-code contract."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from lib.profile_contracts import MarkdownDocument, ParseError, ProfileSelection, ValuePolicy


SKILL_PATH = Path("SKILL.md")
CLI_PATH = Path("CLI_INTERFACE.md")
PORTABLE_EXIT_CODE_RANGE = range(256)


def _success_meaning(value: object | None) -> bool:
    if not ValuePolicy.concrete(value):
        return False

    normalized = re.sub(r"\s+", " ", ValuePolicy.strip_backticks(value)).strip()
    negated_success = re.compile(
        r"\b(?:not|non[-\s]?)\s*(?:success|successful)\b", re.IGNORECASE
    )
    non_success_outcome = re.compile(
        r"\b(?:failure|failed|error|invalid|negative|refusal|refused|denied|"
        r"unsuccessful|timeout|timed\s+out|cancel(?:led|ed)?|aborted|"
        r"interrupted)\b",
        re.IGNORECASE,
    )
    return not negated_success.search(normalized) and not non_success_outcome.search(
        normalized
    )


def run() -> int:
    try:
        selection = ProfileSelection.load(SKILL_PATH)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if selection.template_scaffold() or not selection.selected("packaged-cli"):
        print("CLI exit-code contract is not activated.")
        return 0

    errors: list[str] = []

    if not CLI_PATH.is_file():
        errors.append(
            f"Selected profile 'packaged-cli' requires contract file: {CLI_PATH}"
        )
    else:
        cli = MarkdownDocument.read(CLI_PATH)
        section = cli.section("### Exit codes")

        if section is None or not section.strip():
            errors.append(
                f"{CLI_PATH} requires a non-empty '### Exit codes' section."
            )
        else:
            table_rows: list[tuple[str, str]] = []
            for cells in MarkdownDocument(section, path=CLI_PATH).table_rows():
                if len(cells) != 2:
                    errors.append(
                        f"{CLI_PATH} exit-code mapping rows must contain exactly "
                        f"two columns; found {len(cells)}: {cells!r}."
                    )
                    continue

                code_text, meaning = cells
                if code_text.casefold() == "code":
                    continue
                table_rows.append((code_text, meaning))

            if not table_rows:
                errors.append(f"{CLI_PATH} requires an exit-code mapping table.")
            else:
                rows: list[tuple[int, str]] = []
                for code_text, meaning in table_rows:
                    if re.fullmatch(r"\d+", code_text) is None:
                        errors.append(
                            f"{CLI_PATH} exit code {code_text!r} must be an integer "
                            "in 0..255."
                        )
                        continue

                    code = int(code_text, 10)
                    if code not in PORTABLE_EXIT_CODE_RANGE:
                        errors.append(
                            f"{CLI_PATH} exit code {code} is outside the portable "
                            "process-status range 0..255."
                        )
                        continue
                    rows.append((code, meaning))

                codes = [code for code, _meaning in rows]
                duplicates = sorted(
                    code for code, count in Counter(codes).items() if count > 1
                )
                if duplicates:
                    errors.append(
                        f"{CLI_PATH} exit codes must be unique; duplicated: "
                        f"{', '.join(str(code) for code in duplicates)}."
                    )

                if 0 not in codes:
                    errors.append(
                        f"{CLI_PATH} exit-code mapping must include code 0 for "
                        "successful execution."
                    )
                if not any(code != 0 for code in codes):
                    errors.append(
                        f"{CLI_PATH} exit-code mapping must include at least one "
                        "nonzero outcome or failure code."
                    )

                for code, meaning in rows:
                    if not ValuePolicy.concrete(meaning):
                        errors.append(
                            f"{CLI_PATH} exit code {code} requires a concrete "
                            "caller-visible meaning."
                        )

                zero_meaning = next(
                    (meaning for code, meaning in rows if code == 0),
                    None,
                )
                if zero_meaning is not None and not _success_meaning(zero_meaning):
                    errors.append(
                        f"{CLI_PATH} exit code 0 must denote normal completion and "
                        "must not describe a failure, error, invalid input, refusal, "
                        "negative outcome, timeout, cancellation, or interruption."
                    )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("CLI exit-code contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
