#!/usr/bin/env python3
"""Regression tests for PR review findings in the Python validator foundation."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_ROOT.parents[1]
TEMPLATE_SCRIPT_ROOT = REPOSITORY_ROOT / "template" / ".github" / "scripts"
sys.path.insert(0, str(TEMPLATE_SCRIPT_ROOT))

from lib.profile_contracts import MarkdownDocument, ValuePolicy
from validate_review_followup_contracts import _extract_path


PLACEHOLDER_VALIDATOR = (
    TEMPLATE_SCRIPT_ROOT / "validate_selected_contract_scalar_placeholders.py"
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> int:
    failures: list[str] = []

    def check(name: str, operation) -> None:  # type: ignore[no-untyped-def]
        try:
            operation()
        except Exception as exc:  # noqa: BLE001 - aggregate regression failures.
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    def rejects_nonstandard_whitespace_sentinels() -> None:
        _assert(
            not ValuePolicy.concrete("NOT   SUPPORTED"),
            "multiple-space NOT SUPPORTED was treated as concrete",
        )
        _assert(
            not ValuePolicy.concrete("NOT\tAPPLICABLE"),
            "tab-separated NOT APPLICABLE was treated as concrete",
        )
        _assert(
            not ValuePolicy.resolved_allow_not_supported("NOT \t APPLICABLE"),
            "mixed-whitespace NOT APPLICABLE was treated as resolved",
        )

    def preserves_empty_section_parity() -> None:
        document = MarkdownDocument(
            "## Empty\n## Next\n\nNext value: retained\n"
        )
        _assert(document.section("## Empty") == "", repr(document.section("## Empty")))
        _assert(
            document.section("## Next") == "\nNext value: retained\n",
            repr(document.section("## Next")),
        )

    def reports_absolute_line_and_section_context() -> None:
        with tempfile.TemporaryDirectory(prefix="review-diagnostic-test-") as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text(
                "Selected profiles: script-assisted\n"
                "Canonical command: NOT APPLICABLE\n"
                "Working directory: repository root\n",
                encoding="utf-8",
            )
            (root / "RUNTIME.md").write_text(
                "# Runtime decision record\n"
                "\n"
                "## Status\n"
                "\n"
                "Selection status: TBD\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, str(PLACEHOLDER_VALIDATOR)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            _assert(completed.returncode != 0, "placeholder validator unexpectedly passed")
            _assert(
                "RUNTIME.md:5 (## Status)" in completed.stderr,
                completed.stderr.strip(),
            )

    def rejects_nonportable_repository_paths() -> None:
        _assert(
            _extract_path("`pyproject.toml`") == "pyproject.toml",
            "portable relative path was rejected",
        )
        for value in (
            "`/etc/passwd`",
            "`../outside.toml`",
            "`C:/Windows/win.ini`",
            "`C:\\Windows\\win.ini`",
            "`C:relative\\file.toml`",
            "`folder\\file.toml`",
            "`\\\\server\\share\\file.toml`",
        ):
            _assert(
                _extract_path(value) is None,
                f"non-portable path was accepted: {value}",
            )

    check(
        "rejects nonstandard-whitespace sentinels",
        rejects_nonstandard_whitespace_sentinels,
    )
    check("preserves empty-section parity", preserves_empty_section_parity)
    check(
        "reports absolute line and section context",
        reports_absolute_line_and_section_context,
    )
    check(
        "rejects non-portable repository paths",
        rejects_nonportable_repository_paths,
    )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Python review-fix regression tests passed (4 cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
