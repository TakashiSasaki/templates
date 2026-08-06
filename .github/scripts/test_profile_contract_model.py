#!/usr/bin/env python3
"""Parity tests for the shared Python profile-contract model."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from lib.profile_contracts import (
    MarkdownDocument,
    ParseError,
    ProfileSelection,
    SkillDocument,
    ValuePolicy,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> int:
    failures: list[str] = []

    def check(name: str, operation) -> None:  # type: ignore[no-untyped-def]
        try:
            operation()
        except Exception as exc:  # noqa: BLE001 - aggregate all parity failures.
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    def parses_one_normalized_profile_declaration() -> None:
        with tempfile.TemporaryDirectory(prefix="profile-contract-model-test-") as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text(
                "- Selected profiles: `packaged-cli, mcp-enabled`\n",
                encoding="utf-8",
            )
            selection = ProfileSelection.load(path)
            _assert(
                selection.profiles == ("packaged-cli", "mcp-enabled"),
                repr(selection.profiles),
            )
            _assert(
                selection.selected("packaged-cli"),
                "packaged-cli was not selected",
            )
            _assert(
                not selection.template_scaffold(),
                "concrete selection reported as scaffold",
            )

    def rejects_duplicate_profile_declarations() -> None:
        with tempfile.TemporaryDirectory(prefix="profile-contract-model-test-") as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text(
                "Selected profiles: packaged-cli\n"
                "Selected profiles: mcp-enabled\n",
                encoding="utf-8",
            )
            try:
                ProfileSelection.load(path)
            except ParseError as exc:
                _assert("exactly one" in str(exc), str(exc))
                return
            raise AssertionError("duplicate declarations were accepted")

    def rejects_empty_profile_declaration() -> None:
        with tempfile.TemporaryDirectory(prefix="profile-contract-model-test-") as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text("Selected profiles:\n", encoding="utf-8")
            try:
                ProfileSelection.load(path)
            except ParseError as exc:
                _assert("at least one" in str(exc), str(exc))
                return
            raise AssertionError("empty profile declaration was accepted")

    def extracts_nested_and_peer_markdown_sections() -> None:
        document = MarkdownDocument(
            """## Parent

Parent value: retained

### Child

Child value: retained

## Peer

Peer value: excluded
"""
        )
        parent = document.section("## Parent")
        child = document.section("### Child")
        _assert(parent is not None, "parent section was not found")
        _assert(child is not None, "child section was not found")
        _assert("Child value: retained" in parent, repr(parent))
        _assert("Peer value: excluded" not in parent, repr(parent))
        _assert("Child value: retained" in child, repr(child))

    def normalizes_scalar_fields_and_table_cells() -> None:
        document = MarkdownDocument(
            r"""Mode selector: `--json`

| Item | Value |
|---|---|
| TBD | `JSON` |
| Failure | Validation \| runtime failure |
"""
        )
        _assert(
            document.field("Mode selector") == "--json",
            repr(document.field("Mode selector")),
        )
        rows = document.table_rows()
        _assert(rows[1] == ["TBD", "JSON"], repr(rows))
        _assert(
            rows[-1] == ["Failure", r"Validation \| runtime failure"],
            repr(rows),
        )
        table_values = [
            entry.value for entry in document.each_scalar() if entry.kind == "table"
        ]
        _assert("TBD" in table_values, repr(table_values))
        _assert(r"Validation \| runtime failure" in table_values, repr(table_values))

    def applies_shared_unresolved_and_concrete_value_policy() -> None:
        _assert(ValuePolicy.unresolved_scalar("`TBD`"), "TBD was not unresolved")
        _assert(
            ValuePolicy.unresolved_scalar("details forthcoming"),
            "forthcoming phrase was not unresolved",
        )
        _assert(
            not ValuePolicy.unresolved_scalar("documented behavior"),
            "concrete prose was unresolved",
        )
        _assert(ValuePolicy.resolved("NONE"), "NONE should be resolved")
        _assert(not ValuePolicy.concrete("NONE"), "NONE should not be concrete")
        _assert(
            ValuePolicy.concrete("successful completion"),
            "concrete value was rejected",
        )

    def parses_safe_yaml_frontmatter() -> None:
        document = SkillDocument(
            """---
name: example-skill
description: Example
metadata:
  profiles:
    - instruction-only
---
# Example
""",
            path="SKILL.md",
        )
        _assert(document.metadata["name"] == "example-skill", repr(document.metadata))
        _assert(
            document.metadata["metadata"]["profiles"] == ["instruction-only"],
            repr(document.metadata),
        )

    def rejects_yaml_aliases() -> None:
        try:
            SkillDocument(
                """---
name: &identity example-skill
description: *identity
---
# Example
""",
                path="SKILL.md",
            )
        except ParseError as exc:
            _assert("aliases are not permitted" in str(exc), str(exc))
            return
        raise AssertionError("YAML alias was accepted")

    check(
        "parses one normalized profile declaration",
        parses_one_normalized_profile_declaration,
    )
    check(
        "rejects duplicate profile declarations",
        rejects_duplicate_profile_declarations,
    )
    check(
        "rejects an empty profile declaration",
        rejects_empty_profile_declaration,
    )
    check(
        "extracts nested and peer Markdown sections",
        extracts_nested_and_peer_markdown_sections,
    )
    check(
        "normalizes scalar fields and table cells",
        normalizes_scalar_fields_and_table_cells,
    )
    check(
        "applies shared unresolved and concrete value policy",
        applies_shared_unresolved_and_concrete_value_policy,
    )
    check("parses safe YAML frontmatter", parses_safe_yaml_frontmatter)
    check("rejects YAML aliases", rejects_yaml_aliases)

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Shared Python profile contract model tests passed (8 cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
