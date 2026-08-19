#!/usr/bin/env python3
"""CLI adapter for managed Composition mutation operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import composer_core as core
import composer_transaction as transaction


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply",))
    parser.add_argument("--mode", choices=("update",), required=True)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        if args.config is not None:
            raise core.CompositionError(
                "UPDATE_CONFIG_NOT_ALLOWED",
                "update preserves lock intent and therefore does not accept --config; use upgrade for intent changes",
            )
        status, payload = transaction.apply_update(args.target.absolute())
    except core.CompositionError as exc:
        _emit({"status": "error", "code": exc.code, "message": exc.message})
        return 2
    _emit(payload)
    return status
