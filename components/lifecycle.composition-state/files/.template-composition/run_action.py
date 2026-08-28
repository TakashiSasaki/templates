#!/usr/bin/env python3
"""Dispatch Composition machine actions without exposing provider-internal argv."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_RESULT_SCHEMA = ".template-composition/lifecycle-checkpoint-action-result.schema.json"
READINESS_RESULT_SCHEMA = ".template-composition/implementation-evidence-release-readiness.schema.json"
_BROWSER_ARGUMENTS = (
    ("--browser-binary", frozenset({"available", "unavailable", "not-checked"})),
    ("--webdriver", frozenset({"available", "unavailable", "not-checked"})),
    ("--compatibility", frozenset({"compatible", "incompatible", "not-checked"})),
    ("--localhost", frozenset({"allowed", "restricted", "not-checked"})),
)


def _emit_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True))


def _checkpoint_failure(
    action: str,
    message: str,
    *,
    provider_returncode: int | None = None,
) -> int:
    _emit_json(
        {
            "$schema": CHECKPOINT_RESULT_SCHEMA,
            "schema_version": 1,
            "action": action,
            "status": "failed",
            "provider_returncode": provider_returncode,
            "error": message,
        }
    )
    return 1


def _run_provider(entrypoint: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / entrypoint), *arguments]
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            command,
            126,
            "",
            f"cannot execute provider action: {exc}",
        )


def _load_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _release_readiness() -> int:
    result = _run_provider(
        ".template-composition/validators/validate_implementation_evidence.py",
        [".", "--release-readiness", "--format", "json"],
    )
    value = _load_object(result.stdout)
    if result.returncode not in {0, 1} or value is None:
        detail = result.stderr.strip() or result.stdout.strip() or "provider returned no structured result"
        print(f"ERROR: {detail}", file=sys.stderr)
        return result.returncode if result.returncode not in {0, 1} else 2
    value.setdefault("$schema", READINESS_RESULT_SCHEMA)
    _emit_json(value)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def _browser_prerequisites(arguments: list[str]) -> int:
    if len(arguments) != 2 * len(_BROWSER_ARGUMENTS):
        print(
            "ERROR: diagnose-browser-prerequisites requires four flag/value caller observations",
            file=sys.stderr,
        )
        return 2
    for index, (expected_flag, allowed) in enumerate(_BROWSER_ARGUMENTS):
        flag = arguments[index * 2]
        value = arguments[index * 2 + 1]
        if flag != expected_flag:
            print(
                f"ERROR: browser prerequisite argument {index + 1} must use {expected_flag}",
                file=sys.stderr,
            )
            return 2
        if value not in allowed:
            print(
                f"ERROR: unsupported value for {expected_flag}: {value!r}",
                file=sys.stderr,
            )
            return 2
    result = _run_provider(
        "scripts/browser_prerequisite_diagnostics.py",
        [*arguments, "--format", "json"],
    )
    value = _load_object(result.stdout)
    if result.returncode != 0 or value is None:
        detail = result.stderr.strip() or result.stdout.strip() or "provider returned no structured result"
        print(f"ERROR: {detail}", file=sys.stderr)
        return result.returncode if result.returncode != 0 else 2
    _emit_json(value)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return 0


def _release_candidate(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(
            "ERROR: verify-release-candidate requires exactly one caller value: revision",
            file=sys.stderr,
        )
        return 2
    result = _run_provider(
        ".template-composition/release/verify_candidate.py",
        arguments,
    )
    value = _load_object(result.stdout)
    if result.returncode not in {0, 1} or value is None:
        detail = result.stderr.strip() or result.stdout.strip() or "provider returned no structured result"
        print(f"ERROR: {detail}", file=sys.stderr)
        return result.returncode if result.returncode not in {0, 1} else 2
    _emit_json(value)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def _checkpoint(action: str, arguments: list[str]) -> int:
    if action == "create-planning-checkpoint":
        if len(arguments) != 1:
            return _checkpoint_failure(
                action,
                "expected exactly one caller value: checkpoint_id",
            )
        provider_arguments = ["planning", "--id", arguments[0]]
    elif action == "create-product-checkpoint":
        if len(arguments) != 2:
            return _checkpoint_failure(
                action,
                "expected exactly two caller/provider values: checkpoint_id and latest_checkpoint_id",
            )
        provider_arguments = [
            "product",
            "--id",
            arguments[0],
            "--from",
            arguments[1],
        ]
    else:
        raise AssertionError(f"unexpected checkpoint action: {action}")

    result = _run_provider(
        ".template-composition/checkpoint.py",
        provider_arguments,
    )
    value = _load_object(result.stdout)
    if result.returncode != 0 or value is None:
        detail = result.stderr.strip() or result.stdout.strip() or "checkpoint provider returned no structured result"
        return _checkpoint_failure(
            action,
            detail,
            provider_returncode=result.returncode,
        )
    _emit_json(
        {
            "$schema": CHECKPOINT_RESULT_SCHEMA,
            "schema_version": 1,
            "action": action,
            "status": "completed",
            "provider_returncode": result.returncode,
            "result": value,
        }
    )
    if result.stderr:
        sys.stderr.write(result.stderr)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: missing action identifier", file=sys.stderr)
        return 2
    action = sys.argv[1]
    arguments = sys.argv[2:]
    if action == "check-release-readiness":
        if arguments:
            print("ERROR: check-release-readiness accepts no action arguments", file=sys.stderr)
            return 2
        return _release_readiness()
    if action == "diagnose-browser-prerequisites":
        return _browser_prerequisites(arguments)
    if action == "verify-release-candidate":
        return _release_candidate(arguments)
    if action in {"create-planning-checkpoint", "create-product-checkpoint"}:
        return _checkpoint(action, arguments)
    print(f"ERROR: unknown executable action: {action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
