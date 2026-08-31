#!/usr/bin/env python3
"""Derive deterministic implementation-evidence targets for selected PWA semantics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PWA_CONTRACT_PATHS = {
    "pwa_manifest": "contracts/pwa-manifest.json",
    "pwa_offline": "contracts/pwa-offline.json",
    "pwa_update": "contracts/pwa-update.json",
}
PWA_CONTRACT_IDS = frozenset(PWA_CONTRACT_PATHS)
BROWSER_LEVEL_PROOF_KINDS = ("accessibility-test", "end-to-end-test")
BASE_PROOF_FAMILIES = (
    ("pwa.installability", "pwa_manifest", "installability"),
    ("pwa.application-icon", "pwa_manifest", "application-icon"),
    ("pwa.offline-presentation", "pwa_offline", "offline-presentation"),
    ("pwa.online-revalidation", "pwa_offline", "online-revalidation"),
    ("pwa.update-detection", "pwa_update", "update-detection"),
    ("pwa.update-application", "pwa_update", "update-application"),
)
CACHED_CONTENT_PROOF_FAMILIES = (
    ("pwa.offline-cached-content", "pwa_offline", "offline-cached-content"),
    ("pwa.freshness-unverified", "pwa_offline", "freshness-unverified"),
)
PROOF_FAMILIES = BASE_PROOF_FAMILIES + CACHED_CONTENT_PROOF_FAMILIES


def load_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def target_key(target: object) -> tuple[object, ...]:
    if not isinstance(target, dict):
        return (None, None, None, None)
    return (
        target.get("kind"),
        target.get("contractId"),
        target.get("itemKind"),
        target.get("itemId"),
    )


def target(contract_id: str, item_id: str) -> dict[str, str]:
    return {
        "kind": "contract-item",
        "contractId": contract_id,
        "itemKind": "proof-family",
        "itemId": item_id,
    }


def family_targets(families: tuple[tuple[str, str, str], ...] = PROOF_FAMILIES) -> tuple[dict[str, str], ...]:
    return tuple(target(contract_id, item_id) for _, contract_id, item_id in families)


def family_label(key: tuple[object, ...]) -> str:
    for label, contract_id, item_id in PROOF_FAMILIES:
        if key == ("contract-item", contract_id, "proof-family", item_id):
            return label
    return repr(key)


def pwa_mode(root: Path) -> str:
    modes = {
        contract_id: load_json(root, relative).get("mode")
        for contract_id, relative in PWA_CONTRACT_PATHS.items()
    }
    if len(set(modes.values())) != 1:
        raise ValueError(f"PWA contract modes must match before evidence validation: {modes}")
    mode = next(iter(modes.values()))
    if mode not in {"template", "planning", "product"}:
        raise ValueError(f"unsupported PWA mode for evidence validation: {mode!r}")
    return mode


def active_families(root: Path) -> tuple[tuple[str, str, str], ...]:
    offline = load_json(root, PWA_CONTRACT_PATHS["pwa_offline"])
    policies = offline.get("routePolicies")
    if not isinstance(policies, list) or not policies:
        return PROOF_FAMILIES
    policy_list = [item for item in policies if isinstance(item, dict)]
    if not policy_list:
        return PROOF_FAMILIES
    cached_content = any(item.get("offlineReadBehavior") == "cached-content-when-available" for item in policy_list)
    return BASE_PROOF_FAMILIES + (CACHED_CONTENT_PROOF_FAMILIES if cached_content else ())


def expected_targets(root: Path) -> tuple[dict[str, str], ...]:
    """Return proof-family targets activated by the authoritative PWA route policies."""
    resolved = root.resolve()
    return () if pwa_mode(resolved) == "template" else family_targets(active_families(resolved))
