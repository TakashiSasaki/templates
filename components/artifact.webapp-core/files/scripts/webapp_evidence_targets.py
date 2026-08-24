#!/usr/bin/env python3
"""Derive deterministic Webapp implementation-evidence target inventories."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DOMAIN_IDS = {"surfaces", "routes", "ui_states", "viewports"}
RECORD_ID = re.compile(r"^[a-z][a-z0-9-]*$")


def load_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def target_key(target: dict[str, Any]) -> tuple[Any, ...]:
    if target.get("kind") == "contract-transition":
        return (
            "contract-transition",
            target.get("contractId"),
            target.get("fromVersion"),
            target.get("toVersion"),
        )
    return (
        "contract-item",
        target.get("contractId"),
        target.get("itemKind"),
        target.get("itemId"),
    )


def _sort_key(target: dict[str, Any]) -> str:
    return json.dumps(target, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sorted_unique(targets: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    keys = [target_key(target) for target in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Webapp contracts produce duplicate implementation-evidence targets")
    return tuple(sorted(targets, key=_sort_key))


def expected_targets(root: Path) -> tuple[dict[str, Any], ...]:
    """Return current product targets that every Webapp product must evidence."""
    root = root.resolve()
    surfaces = load_json(root, "contracts/surfaces.json")
    routes = load_json(root, "contracts/routes.json")
    states = load_json(root, "contracts/ui-states.json")
    viewports = load_json(root, "contracts/viewports.json")

    expected: list[dict[str, Any]] = []
    expected.extend(
        {
            "kind": "contract-item",
            "contractId": "surfaces",
            "itemKind": "surface",
            "itemId": item["id"],
        }
        for item in surfaces["surfaces"]
    )
    expected.extend(
        {
            "kind": "contract-item",
            "contractId": "routes",
            "itemKind": "route",
            "itemId": item["id"],
        }
        for item in routes["routes"]
    )
    expected.extend(
        {
            "kind": "contract-item",
            "contractId": "ui_states",
            "itemKind": "ui-state",
            "itemId": item["id"],
        }
        for item in states["states"]
    )
    expected.extend(
        {
            "kind": "contract-item",
            "contractId": "viewports",
            "itemKind": "viewport",
            "itemId": item["id"],
        }
        for item in viewports["viewports"]
    )
    expected.extend(
        {
            "kind": "contract-item",
            "contractId": "viewports",
            "itemKind": "input-capability",
            "itemId": item,
        }
        for item in viewports["inputCapabilities"]
    )
    return _sorted_unique(expected)


def allowed_targets(root: Path) -> tuple[dict[str, Any], ...]:
    """Return required current targets plus optional registered transition targets."""
    root = root.resolve()
    manifest = load_json(root, "contracts/manifest.json")
    allowed = list(expected_targets(root))
    for entry in manifest["contracts"]:
        if entry["id"] not in DOMAIN_IDS:
            continue
        for transition in entry["versionHistory"][1:]:
            allowed.append(
                {
                    "kind": "contract-transition",
                    "contractId": entry["id"],
                    "fromVersion": transition["version"] - 1,
                    "toVersion": transition["version"],
                }
            )
    return _sorted_unique(allowed)


def record_id(target: dict[str, Any]) -> str:
    if target.get("kind") == "contract-transition":
        raw = (
            f"{target['contractId']}-transition-"
            f"{target['fromVersion']}-to-{target['toVersion']}"
        )
    else:
        raw = (
            f"{target['contractId']}-{target['itemKind']}-{target['itemId']}"
        )
    normalized = raw.replace("_", "-")
    if RECORD_ID.fullmatch(normalized) is None:
        raise ValueError(f"cannot derive implementation-evidence record id from {target!r}")
    return normalized
