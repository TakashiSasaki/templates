#!/usr/bin/env python3
"""Validate the declared Bare Worktree local-checkout contract, not live Git state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CONTRACT = Path("contracts/local-checkout-topology.json")
SCHEMA = Path("schemas/local-checkout-topology.schema.json")


class LocalCheckoutTopologyValidationError(RuntimeError):
    """Raised when a local-checkout topology declaration is unsafe or invalid."""


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise LocalCheckoutTopologyValidationError(f"symbolic link is not allowed: {relative}")
    target = root / relative
    if not target.is_file():
        raise LocalCheckoutTopologyValidationError(f"required contract file does not exist: {relative}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalCheckoutTopologyValidationError(f"cannot parse JSON from {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise LocalCheckoutTopologyValidationError(f"{relative} must contain a JSON object")
    return value


def validate_contract(contract: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
        jsonschema.validate(instance=contract, schema=schema)
    except ImportError as exc:
        raise LocalCheckoutTopologyValidationError("jsonschema is required; validation cannot be skipped") from exc
    except Exception as exc:
        raise LocalCheckoutTopologyValidationError(f"contract failed schema validation: {exc}") from exc
    errors: list[str] = []
    if contract.get("topologyKind") != "bare-worktree":
        errors.append("topologyKind must be 'bare-worktree'")
    if contract.get("rootGitIndirection") != "optional-convenience":
        errors.append("rootGitIndirection must be 'optional-convenience'")
    layout = contract.get("layout")
    if not isinstance(layout, dict):
        errors.append("layout must be an object")
    elif layout.get("commonRepositoryBare") is not True or layout.get("linkedWorktrees") != "sibling-directories-under-workspace-root" or layout.get("workspaceRootIsWorktree") is not False:
        errors.append("layout must declare a bare common repository, sibling linked worktrees, and a non-worktree workspace root")
    return errors


def validate_local_checkout_topology(root: Path) -> list[str]:
    return validate_contract(load_json(root, CONTRACT), load_json(root, SCHEMA))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    root = Path(parser.parse_args().root).resolve()
    try:
        errors = validate_local_checkout_topology(root)
    except LocalCheckoutTopologyValidationError as exc:
        print(f"validate_local_checkout_topology.py: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"validate_local_checkout_topology.py: ERROR: {error}", file=sys.stderr)
        return 1
    print("validate_local_checkout_topology.py: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
