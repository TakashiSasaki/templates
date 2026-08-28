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


def _emit_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True))


def _failure(action: str, message: str, *, provider_returncode: int | None = None) -> int:
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


def _checkpoint(action: str, arguments: list[str]) -> int:
    if action == "create-planning-checkpoint":
        if len(arguments) != 1:
            return _failure(action, "expected exactly one caller value: checkpoint_id")
        provider_arguments = ["planning", "--id", arguments[0]]
    elif action == "create-product-checkpoint":
        if len(arguments) != 2:
            return _failure(
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
        return _failure("unknown", f"unsupported checkpoint action: {action}")

    result = _run_provider(
        ".template-composition/checkpoint.py",
        provider_arguments,
    )
    value = _load_object(result.stdout)
    if result.returncode != 0 or value is None:
        detail = result.stderr.strip() or result.stdout.strip() or "checkpoint provider returned no structured result"
        return _failure(action, detail, provider_returncode=result.returncode)
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
        return _failure("unknown", "missing action identifier")
    action = sys.argv[1]
    arguments = sys.argv[2:]
    if action == "check-release-readiness":
        if arguments:
            print("ERROR: check-release-readiness accepts no action arguments", file=sys.stderr)
            return 2
        return _release_readiness()
    if action in {"create-planning-checkpoint", "create-product-checkpoint"}:
        return _checkpoint(action, arguments)
    return _failure("unknown", f"unknown executable action: {action}")


if __name__ == "__main__":
    raise SystemExit(main())
