#!/usr/bin/env python3
"""Derive deterministic Website implementation-evidence target inventories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BROWSER_LEVEL_PROOF_KINDS = ("accessibility-test", "end-to-end-test")
BROWSER_SENSITIVE_CONTRACT_ITEMS = frozenset({
    ("browser_identity", "proof-family"),
    ("site_structure", "page"),
    ("document_metadata", "page-metadata"),
    ("viewports", "viewport"),
    ("viewports", "input-capability"),
})


def load(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def target_key(target: dict[str, Any]) -> tuple[Any, ...]:
    return (target.get("kind"), target.get("contractId"), target.get("itemKind"), target.get("itemId"))


def requires_browser_level_proof(target: object) -> bool:
    return isinstance(target, dict) and target.get("kind") == "contract-item" and (target.get("contractId"), target.get("itemKind")) in BROWSER_SENSITIVE_CONTRACT_ITEMS


def expected_targets(root: Path) -> tuple[dict[str, str], ...]:
    root = root.resolve()
    structure = load(root, "contracts/site-structure.json")
    metadata = load(root, "contracts/document-metadata.json")
    discovery = load(root, "contracts/site-discovery.json")
    viewports = load(root, "contracts/viewports.json")
    targets: list[dict[str, str]] = [
        {"kind": "contract-item", "contractId": "browser_identity", "itemKind": "proof-family", "itemId": "browser-identity"}
    ]
    targets.extend({"kind": "contract-item", "contractId": "site_structure", "itemKind": "page", "itemId": item["id"]} for item in structure["pages"])
    targets.extend({"kind": "contract-item", "contractId": "document_metadata", "itemKind": "page-metadata", "itemId": item["pageId"]} for item in metadata["pages"])
    targets.extend([
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "canonical-origin"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "robots"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "sitemap"},
    ])
    targets.extend({"kind": "contract-item", "contractId": "site_discovery", "itemKind": "feed", "itemId": item["id"]} for item in discovery["feeds"])
    targets.extend({"kind": "contract-item", "contractId": "viewports", "itemKind": "viewport", "itemId": item["id"]} for item in viewports["viewports"])
    targets.extend({"kind": "contract-item", "contractId": "viewports", "itemKind": "input-capability", "itemId": item} for item in viewports["inputCapabilities"])
    keys = [target_key(target) for target in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Website contracts produce duplicate implementation-evidence targets")
    return tuple(sorted(targets, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))))
