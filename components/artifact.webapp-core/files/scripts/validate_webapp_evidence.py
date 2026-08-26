#!/usr/bin/env python3
"""Validate Webapp-specific implementation-evidence coverage and proof strength."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .webapp_evidence_targets import allowed_targets, expected_targets, target_key
else:
    from webapp_evidence_targets import allowed_targets, expected_targets, target_key


BROWSER_INTERACTION = "browser-interaction"
BROWSER_LEVEL_PROOF_KINDS = frozenset({"accessibility-test", "end-to-end-test"})
BROWSER_SENSITIVE_ITEM_KINDS = frozenset({"input-capability", "viewport"})


def load(root: Path, relative: str) -> object:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def actual_targets(evidence: object) -> list[tuple[Any, ...]]:
    if not isinstance(evidence, dict):
        raise TypeError("implementation evidence root must be a JSON object")

    records = evidence.get("records")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")

    actual: list[tuple[Any, ...]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"implementation evidence record {index} must be a JSON object")
        target = record.get("target")
        if not isinstance(target, dict):
            raise TypeError(
                f"implementation evidence record {index} target must be a JSON object"
            )
        actual.append(target_key(target))
    return actual


def _route_requires_browser_interaction(root: Path, target: dict[str, Any]) -> bool:
    if not (
        target.get("kind") == "contract-item"
        and target.get("contractId") == "routes"
        and target.get("itemKind") == "route"
    ):
        return False
    routes = load(root, "contracts/routes.json")
    if not isinstance(routes, dict) or not isinstance(routes.get("routes"), list):
        raise TypeError("routes contract must contain a routes array")
    item_id = target.get("itemId")
    for route in routes["routes"]:
        if not isinstance(route, dict) or route.get("id") != item_id:
            continue
        accessibility = route.get("accessibility")
        return (
            isinstance(accessibility, dict)
            and isinstance(accessibility.get("focusTarget"), str)
            and bool(accessibility["focusTarget"])
        )
    raise KeyError(f"route evidence target does not resolve to a route: {item_id!r}")


def requires_browser_interaction(root: Path, target: object) -> bool:
    if not isinstance(target, dict) or target.get("kind") != "contract-item":
        return False
    if (
        target.get("contractId") == "viewports"
        and target.get("itemKind") in BROWSER_SENSITIVE_ITEM_KINDS
    ):
        return True
    return _route_requires_browser_interaction(root, target)


def browser_interaction_proof_errors(root: Path, evidence: dict[str, Any]) -> list[str]:
    records = evidence.get("records")
    if not isinstance(records, list):
        raise TypeError("implementation evidence records must be a JSON array")

    errors: list[str] = []
    allowed_kinds = ", ".join(sorted(BROWSER_LEVEL_PROOF_KINDS))
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(f"implementation evidence record {index} must be a JSON object")
        target = record.get("target")
        if not requires_browser_interaction(root, target):
            continue
        if not isinstance(target, dict):
            raise TypeError(
                f"implementation evidence record {index} target must be a JSON object"
            )
        key = target_key(target)
        for field, label in (
            ("positiveEvidence", "positive"),
            ("negativeEvidence", "negative"),
        ):
            proofs = record.get(field)
            if not isinstance(proofs, list):
                raise TypeError(
                    f"implementation evidence record {index} {field} must be a JSON array"
                )
            browser_proofs = [
                proof
                for proof in proofs
                if isinstance(proof, dict)
                and proof.get("executionClass") == BROWSER_INTERACTION
            ]
            if not browser_proofs:
                errors.append(
                    f"browser-sensitive Webapp target {key} requires at least one "
                    f"{label} proof with executionClass={BROWSER_INTERACTION!r}; "
                    "static inspection or process integration is not browser interaction"
                )
                continue
            kinds = {
                proof.get("kind")
                for proof in browser_proofs
                if isinstance(proof.get("kind"), str)
            }
            if kinds.isdisjoint(BROWSER_LEVEL_PROOF_KINDS):
                errors.append(
                    f"browser-sensitive Webapp target {key} requires its {label} "
                    f"browser-interaction proof to use a browser-level proof kind "
                    f"({allowed_kinds})"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Webapp repository root; defaults to the current directory",
    )
    args = parser.parse_args()
    root = Path(args.root)

    try:
        evidence = load(root, "contracts/implementation-evidence.json")
        if not isinstance(evidence, dict):
            raise TypeError("implementation evidence root must be a JSON object")
        if evidence.get("mode") == "template":
            print("Webapp evidence coverage: template mode OK")
            return 0
        actual = actual_targets(evidence)
        strength_errors = browser_interaction_proof_errors(root, evidence)
    except (AttributeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot load Webapp implementation evidence: {exc}", file=sys.stderr)
        return 1

    errors = []
    seen: set[tuple[Any, ...]] = set()
    duplicates: set[tuple[Any, ...]] = set()
    for item in actual:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    for duplicate in sorted(duplicates, key=str):
        errors.append(f"duplicate Webapp implementation-evidence target: {duplicate}")

    try:
        expected = {target_key(target) for target in expected_targets(root)}
        allowed = {target_key(target) for target in allowed_targets(root)}
    except (AttributeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot derive Webapp implementation-evidence targets: {exc}", file=sys.stderr)
        return 1

    actual_set = set(actual)
    for missing in sorted(expected - actual_set, key=str):
        errors.append(f"missing Webapp implementation-evidence target: {missing}")
    for extra in sorted(actual_set - allowed, key=str):
        errors.append(f"unknown Webapp implementation-evidence target: {extra}")
    errors.extend(strength_errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Webapp evidence coverage and proof strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
