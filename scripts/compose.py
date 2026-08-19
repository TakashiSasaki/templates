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
    mode = _mode_from_argv()
    if mode is None:
        return _initial_main()
    if mode == "initial":
        _remove_initial_mode()
        return _initial_main()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "update" and command == "apply":
        from composer_apply import main as apply_main

        return apply_main()
    from composer_managed import main as managed_main

    return managed_main()


if __name__ == "__main__":
    raise SystemExit(main())
