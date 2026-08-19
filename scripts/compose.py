#!/usr/bin/env python3
"""Resolve, plan, materialize, inspect, and validate composition consumers."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from composer_core import CompositionError, _assert_tracked_authority, main as _initial_main

__all__ = ["CompositionError", "_assert_tracked_authority", "main"]

COMMANDS = {"inspect", "plan", "apply", "validate"}
VALUE_OPTIONS = {"--mode", "--config", "--target"}


def _normalize_command_position() -> None:
    arguments = sys.argv[1:]
    if not arguments or arguments[0] in COMMANDS:
        return
    command_index: int | None = None
    skip_next = False
    for index, argument in enumerate(arguments):
        if skip_next:
            skip_next = False
            continue
        if argument in VALUE_OPTIONS:
            skip_next = True
            continue
        if any(argument.startswith(option + "=") for option in VALUE_OPTIONS):
            continue
        if argument in COMMANDS:
            command_index = index
            break
    if command_index is None:
        return
    command = arguments[command_index]
    sys.argv[:] = [
        sys.argv[0],
        command,
        *arguments[:command_index],
        *arguments[command_index + 1 :],
    ]


def _mode_from_argv() -> str | None:
    arguments = sys.argv[1:]
    for index, argument in enumerate(arguments):
        if argument == "--mode":
            if index + 1 >= len(arguments):
                return ""
            return arguments[index + 1]
        if argument.startswith("--mode="):
            return argument.split("=", 1)[1]
    return None


def _remove_initial_mode() -> None:
    arguments = sys.argv[1:]
    rewritten: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--mode" and index + 1 < len(arguments) and arguments[index + 1] == "initial":
            index += 2
            continue
        if argument == "--mode=initial":
            index += 1
            continue
        rewritten.append(argument)
        index += 1
    sys.argv[:] = [sys.argv[0], *rewritten]


def main() -> int:
    _normalize_command_position()
    mode = _mode_from_argv()
    if mode is None:
        return _initial_main()
    if mode == "initial":
        _remove_initial_mode()
        return _initial_main()
    if mode == "upgrade":
        from composer_upgrade import main as upgrade_main

        return upgrade_main()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "update" and command == "apply":
        from composer_apply import main as apply_main

        return apply_main()
    from composer_managed import main as managed_main

    return managed_main()


if __name__ == "__main__":
    raise SystemExit(main())
