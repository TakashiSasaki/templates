#!/usr/bin/env python3
"""Resolve, plan, materialize, inspect, and validate composition consumers."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from composer_cli_messages import remediate_payload
from composer_core import (
    LOCK_RELATIVE,
    TRANSACTION_RELATIVE,
    CompositionError,
    _assert_tracked_authority,
    load_json_bytes,
    main as _initial_main,
    validate_consumer_with_source_validator,
)
from composer_post_apply import build_post_apply_guidance

__all__ = ["CompositionError", "_assert_tracked_authority", "main"]

COMMANDS = {"inspect", "plan", "apply", "validate"}
VALUE_OPTIONS = {"--mode", "--config", "--target"}
SELECTED_VALIDATION_RUNNER = ".template-composition/validate.py"

PUBLIC_HELP = """\
usage: compose.py COMMAND [--mode MODE] --target PATH [--config FILE]

Public lifecycle:
  inspect -> plan -> apply -> validate

Commands:
  inspect   Classify target state without mutation.
  plan      Preview deterministic initial/update/upgrade changes.
  apply     Materialize or reconcile the selected lifecycle operation.
  validate  Validate Composition state and validators required by resolved components.

Modes for plan/apply:
  initial   Default when --mode is omitted. New composition; --config is required.
  update    Preserve normalized lock-v2 intent; --config is forbidden.
  upgrade   Explicit intent/compatibility-boundary change; --config is required for a
            new plan/apply and forbidden when recovering an interrupted upgrade.

Recovery:
  If inspect reports managed-interrupted, use the exact Composition source revision
  recorded in .template-composition/transaction.json and rerun the matching apply mode.
  Do not delete the transaction marker manually. Interrupted update and upgrade recovery
  both omit --config.

Examples:
  python scripts/compose.py inspect --target /repo
  python scripts/compose.py plan --config composition.json --target /repo
  python scripts/compose.py apply --config composition.json --target /repo
  python scripts/compose.py plan --mode update --target /repo
  python scripts/compose.py apply --mode update --target /repo
  python scripts/compose.py plan --mode upgrade --config composition.json --target /repo
  python scripts/compose.py apply --mode upgrade --config composition.json --target /repo
  python scripts/compose.py validate --target /repo

See docs/consumer-guide.md for task-oriented use and docs/reference/composer.md for the
exact consumer-facing contract.
"""


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


def _argument_value(option: str) -> str | None:
    arguments = sys.argv[1:]
    for index, argument in enumerate(arguments):
        if argument == option:
            if index + 1 >= len(arguments):
                return None
            return arguments[index + 1]
        if argument.startswith(option + "="):
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


def _read_regular_json_object(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        raw = path.read_bytes()
        value = load_json_bytes(raw, label=str(path))
    except (OSError, CompositionError):
        return None
    return value if isinstance(value, dict) else None


def _previous_lock_for_apply() -> dict[str, Any] | None:
    target_value = _argument_value("--target")
    if target_value is None:
        return None
    target = Path(target_value).absolute()

    transaction = _read_regular_json_object(target / TRANSACTION_RELATIVE)
    if transaction is not None:
        old_lock = transaction.get("old_lock")
        if isinstance(old_lock, dict):
            return old_lock

    return _read_regular_json_object(target / LOCK_RELATIVE)


def _add_post_apply_guidance(
    payload: dict[str, Any],
    previous_lock: dict[str, Any] | None,
) -> None:
    if payload.get("status") not in {"applied", "updated", "upgraded"}:
        return
    target_value = payload.get("target")
    if not isinstance(target_value, str):
        return
    final_lock = _read_regular_json_object(Path(target_value) / LOCK_RELATIVE)
    if final_lock is None:
        return
    payload.update(
        build_post_apply_guidance(
            final_lock,
            previous_lock=previous_lock,
        )
    )


def _run_adapter(
    adapter: Callable[[], int],
    *,
    remediate: bool,
    post_apply: bool,
) -> int:
    """Run an internal adapter and present its public JSON response."""

    previous_lock = _previous_lock_for_apply() if post_apply else None
    stream = io.StringIO()
    try:
        with redirect_stdout(stream):
            status = adapter()
    except SystemExit as exc:
        rendered = stream.getvalue()
        if rendered:
            print(rendered, end="")
        return exc.code if isinstance(exc.code, int) else 1

    rendered = stream.getvalue()
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError:
        print(rendered, end="")
        return status
    if not isinstance(payload, dict):
        print(rendered, end="")
        return status

    presented = remediate_payload(payload) if remediate else payload
    if status == 0 and post_apply:
        _add_post_apply_guidance(presented, previous_lock)
    print(json.dumps(presented, ensure_ascii=False, indent=2))
    return status


def _run_managed_adapter(adapter: Callable[[], int], *, post_apply: bool = False) -> int:
    """Run an internal managed adapter and improve its public JSON presentation."""

    return _run_adapter(adapter, remediate=True, post_apply=post_apply)


def _emit_validation(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _validation_error(target: Path, message: str) -> int:
    _emit_validation(
        {
            "status": "invalid",
            "target": str(target),
            "errors": [message],
            "resolved_components": [],
            "checks": [],
        }
    )
    return 2


def _failed_check_messages(checks: object) -> list[str]:
    if not isinstance(checks, list):
        return ["selected-component validator returned an invalid checks field"]
    errors: list[str] = []
    for check in checks:
        if not isinstance(check, dict) or check.get("status") != "failed":
            continue
        check_id = check.get("id", "unknown")
        detail = check.get("stderr") or check.get("stdout") or "validation failed"
        if not isinstance(detail, str):
            detail = repr(detail)
        errors.append(f"{check_id}: {detail.strip()}")
    return errors


def _run_public_validation() -> int:
    parser = argparse.ArgumentParser(prog=Path(sys.argv[0]).name)
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:])
    target = args.target.absolute()

    try:
        state_valid, state_errors = validate_consumer_with_source_validator(target)
    except CompositionError as exc:
        return _validation_error(target, exc.message)
    if not state_valid:
        _emit_validation(
            {
                "status": "invalid",
                "target": str(target),
                "errors": state_errors,
                "resolved_components": [],
                "checks": [],
            }
        )
        return 2

    runner = target / SELECTED_VALIDATION_RUNNER
    if runner.is_symlink() or not runner.is_file():
        return _validation_error(
            target,
            "selected-component validation entrypoint is missing or unsafe: "
            f"{SELECTED_VALIDATION_RUNNER}; cross the lifecycle.composition-state component-version boundary with an explicit upgrade",
        )

    process = subprocess.run(
        [sys.executable, str(runner), str(target), "--format", "json"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        return _validation_error(
            target,
            "selected-component validation entrypoint did not emit JSON: "
            f"{exc}; stderr={process.stderr.strip()!r}",
        )
    if not isinstance(result, dict):
        return _validation_error(target, "selected-component validation result must be a JSON object")

    status = result.get("status")
    checks = result.get("checks")
    errors = _failed_check_messages(checks)
    if status not in {"valid", "invalid"}:
        errors.append(f"selected-component validation returned unsupported status: {status!r}")
        status = "invalid"
    if process.returncode == 0 and status != "valid":
        errors.append("selected-component validation returned exit code 0 for a non-valid result")
        status = "invalid"
    if process.returncode != 0 and status == "valid":
        errors.append(
            "selected-component validation returned a nonzero exit code for a valid result: "
            f"{process.returncode}"
        )
        status = "invalid"
    if process.stderr.strip():
        errors.append(f"selected-component validation stderr: {process.stderr.strip()}")
        status = "invalid"

    _emit_validation(
        {
            "status": status,
            "target": str(target),
            "errors": errors,
            "resolved_components": result.get("resolved_components", []),
            "checks": checks if isinstance(checks, list) else [],
        }
    )
    return 0 if status == "valid" and not errors else 2


def main() -> int:
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(PUBLIC_HELP, end="")
        return 0

    _normalize_command_position()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "validate":
        return _run_public_validation()

    mode = _mode_from_argv()
    if mode is None:
        if command == "apply":
            return _run_adapter(_initial_main, remediate=False, post_apply=True)
        return _initial_main()
    if mode == "initial":
        _remove_initial_mode()
        if command == "apply":
            return _run_adapter(_initial_main, remediate=False, post_apply=True)
        return _initial_main()
    if mode == "upgrade":
        from composer_upgrade import main as upgrade_main

        return _run_managed_adapter(upgrade_main, post_apply=command == "apply")
    if mode == "update" and command == "apply":
        from composer_apply import main as apply_main

        return _run_managed_adapter(apply_main, post_apply=True)
    from composer_update_plan import main as update_plan_main

    return _run_managed_adapter(update_plan_main)


if __name__ == "__main__":
    raise SystemExit(main())
