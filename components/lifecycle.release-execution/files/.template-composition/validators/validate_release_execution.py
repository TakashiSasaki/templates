#!/usr/bin/env python3
"""Validate product-owned release execution bindings against implementation evidence."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from contract_common import load_json


_DRIVE_PREFIX_PATTERN = re.compile(r"^[A-Za-z]:")
_REPOSITORY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_WORKING_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9._-]*$")


def _index(items: object, key: str, label: str) -> tuple[dict[str, dict], list[str]]:
    errors: list[str] = []
    if not isinstance(items, list):
        return {}, [f"{label} must be an array"]
    result: dict[str, dict] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label} entry {index} must be an object")
            continue
        value = item.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{label} entry {index} requires {key}")
            continue
        if value in result:
            errors.append(f"duplicate {label} {key}: {value}")
            continue
        result[value] = item
    return result, errors


def _implementation_harness_locator(command: dict) -> str | None:
    execution = command.get("execution")
    if not isinstance(execution, dict):
        return None
    harness = execution.get("harness")
    if not isinstance(harness, dict):
        return None
    locator = harness.get("locator")
    return locator if isinstance(locator, str) and locator else None


def _safe_repository_path(value: str, *, allow_dot: bool) -> bool:
    """Mirror the schema's traversal/absolute/.git safety boundary for direct callers."""

    if allow_dot and value == ".":
        return True
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or _DRIVE_PREFIX_PATTERN.match(value)
    ):
        return False
    segment_pattern = (
        _WORKING_SEGMENT_PATTERN if allow_dot else _REPOSITORY_SEGMENT_PATTERN
    )
    parts = value.split("/")
    return bool(parts) and all(
        part not in {"", ".", ".."}
        and part.lower() != ".git"
        and segment_pattern.fullmatch(part) is not None
        for part in parts
    )


def _expected_harness_argument(
    working_directory: str, harness_locator: str
) -> str | None:
    """Return the traversal-free argv token that resolves to the root-relative harness."""

    if working_directory == ".":
        return harness_locator
    prefix = working_directory.rstrip("/") + "/"
    if not harness_locator.startswith(prefix):
        return None
    relative = harness_locator[len(prefix) :]
    return relative or None


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        implementation = load_json(root / "contracts/implementation-evidence.json")
        execution = load_json(root / "contracts/release-execution.json")
    except Exception as exc:
        return [f"cannot load release execution inputs: {exc}"]

    if not isinstance(implementation, dict):
        return ["implementation evidence must be an object"]
    if not isinstance(execution, dict):
        return ["release execution must be an object"]

    implementation_mode = implementation.get("mode")
    execution_mode = execution.get("mode")

    implementation_commands, command_errors = _index(
        implementation.get("commands", []), "id", "implementation command"
    )
    errors.extend(command_errors)
    execution_commands, execution_errors = _index(
        execution.get("commands", []), "commandId", "release execution command"
    )
    errors.extend(execution_errors)

    if execution_mode == "template":
        if execution_commands:
            errors.append("template release execution must not contain command bindings")
        if implementation_mode == "product":
            errors.append(
                "product implementation evidence requires product release execution"
            )
        elif implementation_mode not in {"template", "planning"}:
            errors.append(
                f"unsupported implementation-evidence mode: {implementation_mode!r}"
            )
        return errors

    if execution_mode != "product":
        return [*errors, f"unsupported release-execution mode: {execution_mode!r}"]
    if implementation_mode != "product":
        errors.append("product release execution requires product implementation evidence")
        return errors

    expected_ids = set(implementation_commands)
    actual_ids = set(execution_commands)
    if actual_ids != expected_ids:
        errors.append(
            "release execution commands must exactly cover authoritative commands: "
            f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}"
        )

    for command_id, binding in execution_commands.items():
        argv = binding.get("argv")
        argv_valid = isinstance(argv, list) and bool(argv) and all(
            isinstance(argument, str) and argument and "\x00" not in argument
            for argument in argv
        )
        if not argv_valid:
            errors.append(
                f"release execution command {command_id}: argv must be a non-empty array of non-empty NUL-free strings"
            )
        working_directory = binding.get("workingDirectory")
        working_directory_valid = (
            isinstance(working_directory, str)
            and _safe_repository_path(working_directory, allow_dot=True)
        )
        if not working_directory_valid:
            errors.append(
                f"release execution command {command_id}: workingDirectory must be a safe repository-relative directory"
            )
        harness_locator = binding.get("harnessLocator")
        harness_locator_valid = (
            isinstance(harness_locator, str)
            and _safe_repository_path(harness_locator, allow_dot=False)
        )
        if not harness_locator_valid:
            errors.append(
                f"release execution command {command_id}: harnessLocator must be a safe repository-relative file path"
            )
            continue
        assert isinstance(harness_locator, str)
        harness_argument_index = binding.get("harnessArgumentIndex")
        index_valid = (
            isinstance(harness_argument_index, int)
            and not isinstance(harness_argument_index, bool)
            and harness_argument_index >= 0
        )
        if not index_valid:
            errors.append(
                f"release execution command {command_id}: harnessArgumentIndex must be a non-negative integer"
            )
        elif argv_valid:
            assert isinstance(argv, list)
            if harness_argument_index >= len(argv):
                errors.append(
                    f"release execution command {command_id}: harnessArgumentIndex {harness_argument_index} is outside argv"
                )
            elif working_directory_valid:
                assert isinstance(working_directory, str)
                expected_argument = _expected_harness_argument(
                    working_directory, harness_locator
                )
                if expected_argument is None:
                    errors.append(
                        f"release execution command {command_id}: harnessLocator {harness_locator!r} "
                        f"must be inside workingDirectory {working_directory!r} without traversal"
                    )
                elif argv[harness_argument_index] != expected_argument:
                    errors.append(
                        f"release execution command {command_id}: argv[{harness_argument_index}] "
                        f"must select harnessLocator {harness_locator!r} from workingDirectory "
                        f"{working_directory!r} using exact argument {expected_argument!r}, "
                        f"got {argv[harness_argument_index]!r}"
                    )
        authoritative = implementation_commands.get(command_id)
        if authoritative is None:
            continue
        expected_harness = _implementation_harness_locator(authoritative)
        if expected_harness is None:
            errors.append(
                f"implementation command {command_id}: execution harness locator is required before release binding"
            )
        elif harness_locator != expected_harness:
            errors.append(
                f"release execution command {command_id}: harnessLocator must exactly match "
                f"implementation execution harness {expected_harness!r}, got {harness_locator!r}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Release execution validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
