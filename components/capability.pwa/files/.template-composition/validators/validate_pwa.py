#!/usr/bin/env python3
"""Validate Progressive Web App contracts against Webapp semantic authority."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PWA_MANIFEST = Path("contracts/pwa-manifest.json")
PWA_OFFLINE = Path("contracts/pwa-offline.json")
PWA_UPDATE = Path("contracts/pwa-update.json")
ROUTES = Path("contracts/routes.json")
SURFACES = Path("contracts/surfaces.json")
UI_STATES = Path("contracts/ui-states.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def indexed(items: object, *, collection: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(items, list):
        return {}, [f"{collection} must be an array"]
    errors: list[str] = []
    values: dict[str, dict[str, Any]] = {}
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append(f"every {collection} item must be an object with a text id")
            continue
        item_id = item["id"]
        ids.append(item_id)
        values.setdefault(item_id, item)
    for duplicate, count in sorted(Counter(ids).items()):
        if count > 1:
            errors.append(f"duplicate {collection} id: {duplicate}")
    return values, errors


def path_in_scope(path: str, scope: str) -> bool:
    return scope == "/" or path.startswith(scope)


def state_reference(
    errors: list[str],
    states: dict[str, dict[str, Any]],
    state_id: object,
    *,
    field: str,
    categories: frozenset[str] | None = None,
) -> None:
    if not isinstance(state_id, str):
        return
    state = states.get(state_id)
    if state is None:
        errors.append(f"{field} references unknown UI state {state_id!r}")
        return
    if categories is not None and state.get("category") not in categories:
        errors.append(
            f"{field} UI state {state_id!r} must have category one of {', '.join(sorted(categories))}"
        )


def validate_manifest(
    manifest: dict[str, Any],
    routes: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    route_id = manifest.get("startRouteId")
    scope = manifest.get("scope")
    if isinstance(route_id, str):
        route = routes.get(route_id)
        if route is None:
            errors.append(f"PWA startRouteId references unknown route {route_id!r}")
        else:
            if route.get("canonical") is not True:
                errors.append(f"PWA start route {route_id!r} must be canonical")
            if route.get("deepLink") is not True:
                errors.append(f"PWA start route {route_id!r} must be deep-linkable")
            path = route.get("path")
            if isinstance(path, str) and isinstance(scope, str) and not path_in_scope(path, scope):
                errors.append(
                    f"PWA start route {route_id!r} path {path!r} is outside manifest scope {scope!r}"
                )

    icons = manifest.get("icons")
    if isinstance(icons, list):
        icon_ids = [icon.get("id") for icon in icons if isinstance(icon, dict) and isinstance(icon.get("id"), str)]
        icon_hrefs = [icon.get("href") for icon in icons if isinstance(icon, dict) and isinstance(icon.get("href"), str)]
        for duplicate, count in sorted(Counter(icon_ids).items()):
            if count > 1:
                errors.append(f"duplicate PWA manifest icon id: {duplicate}")
        for duplicate, count in sorted(Counter(icon_hrefs).items()):
            if count > 1:
                errors.append(f"duplicate PWA manifest icon href: {duplicate}")
    return errors


def validate_offline(
    offline: dict[str, Any],
    manifest: dict[str, Any],
    routes: dict[str, dict[str, Any]],
    surfaces: dict[str, dict[str, Any]],
    states: dict[str, dict[str, Any]],
) -> list[str]:
    if offline.get("availability") == "network-only":
        return []
    if offline.get("availability") != "offline-capable":
        return [f"unsupported PWA offline availability: {offline.get('availability')!r}"]

    errors: list[str] = []
    controlled = offline.get("controlledRouteIds")
    service_scope = offline.get("serviceWorkerScope")
    manifest_scope = manifest.get("scope")
    controlled_surfaces: set[str] = set()
    controlled_ids = set(controlled) if isinstance(controlled, list) else set()
    if isinstance(controlled, list):
        for route_id in controlled:
            if not isinstance(route_id, str):
                continue
            route = routes.get(route_id)
            if route is None:
                errors.append(f"PWA controlledRouteIds references unknown route {route_id!r}")
                continue
            path = route.get("path")
            if isinstance(path, str) and isinstance(service_scope, str) and not path_in_scope(path, service_scope):
                errors.append(
                    f"PWA controlled route {route_id!r} path {path!r} is outside serviceWorkerScope {service_scope!r}"
                )
            if isinstance(path, str) and isinstance(manifest_scope, str) and not path_in_scope(path, manifest_scope):
                errors.append(
                    f"PWA controlled route {route_id!r} path {path!r} is outside manifest scope {manifest_scope!r}"
                )
            surface_id = route.get("surface")
            if isinstance(surface_id, str):
                controlled_surfaces.add(surface_id)

    fallback = offline.get("navigationFallbackRouteId")
    if isinstance(fallback, str):
        if fallback not in routes:
            errors.append(f"PWA navigationFallbackRouteId references unknown route {fallback!r}")
        elif fallback not in controlled_ids:
            errors.append("PWA navigation fallback route must be included in controlledRouteIds")

    state_reference(
        errors,
        states,
        offline.get("offlineStateId"),
        field="offlineStateId",
        categories=frozenset({"connectivity", "degraded"}),
    )

    policies = offline.get("surfacePolicies")
    policy_surfaces: set[str] = set()
    if isinstance(policies, list):
        for policy in policies:
            if not isinstance(policy, dict):
                continue
            surface_id = policy.get("surfaceId")
            if not isinstance(surface_id, str):
                continue
            if surface_id in policy_surfaces:
                errors.append(f"duplicate PWA offline surface policy: {surface_id}")
                continue
            policy_surfaces.add(surface_id)
            surface = surfaces.get(surface_id)
            if surface is None:
                errors.append(f"PWA offline surface policy references unknown surface {surface_id!r}")
                continue
            declared = set(surface.get("dataClassifications", []))
            cacheable = set(policy.get("cacheableDataClassifications", []))
            unknown = cacheable - declared
            if unknown:
                errors.append(
                    f"PWA offline surface {surface_id!r} marks undeclared data classifications cacheable: {sorted(unknown)}"
                )
    if policy_surfaces != controlled_surfaces:
        missing = sorted(controlled_surfaces - policy_surfaces)
        extra = sorted(policy_surfaces - controlled_surfaces)
        if missing:
            errors.append(f"PWA offline controlled surfaces are missing explicit cache policies: {missing}")
        if extra:
            errors.append(f"PWA offline surface policies do not belong to controlled routes: {extra}")

    mutation = offline.get("mutationBehavior")
    if mutation == "queue-until-online":
        state_reference(
            errors,
            states,
            offline.get("pendingStateId"),
            field="pendingStateId",
            categories=frozenset({"progress", "connectivity"}),
        )
        state_reference(
            errors,
            states,
            offline.get("failureStateId"),
            field="failureStateId",
            categories=frozenset({"error", "degraded", "connectivity"}),
        )
    elif "pendingStateId" in offline or "failureStateId" in offline:
        errors.append("pendingStateId/failureStateId are only valid when mutationBehavior is queue-until-online")
    return errors


def validate_update(update: dict[str, Any], states: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    activation = update.get("activation")
    if activation == "user-confirmed":
        state_reference(
            errors,
            states,
            update.get("updateAvailableStateId"),
            field="updateAvailableStateId",
        )
    elif "updateAvailableStateId" in update:
        errors.append("updateAvailableStateId is only valid when activation is user-confirmed")

    if "applyingStateId" in update:
        state_reference(
            errors,
            states,
            update.get("applyingStateId"),
            field="applyingStateId",
            categories=frozenset({"progress"}),
        )
    if "failureStateId" in update:
        state_reference(
            errors,
            states,
            update.get("failureStateId"),
            field="failureStateId",
            categories=frozenset({"error", "degraded"}),
        )
    if activation == "immediate" and update.get("unsavedChangesPolicy") == "block-activation":
        errors.append("immediate PWA update activation cannot use block-activation unsavedChangesPolicy")
    return errors


def validate(root: Path) -> list[str]:
    manifest = load_json(root, PWA_MANIFEST)
    offline = load_json(root, PWA_OFFLINE)
    update = load_json(root, PWA_UPDATE)
    routes_document = load_json(root, ROUTES)
    surfaces_document = load_json(root, SURFACES)
    states_document = load_json(root, UI_STATES)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)

    errors: list[str] = []
    modes = {
        "pwa-manifest": manifest.get("mode"),
        "pwa-offline": offline.get("mode"),
        "pwa-update": update.get("mode"),
    }
    if len(set(modes.values())) != 1:
        errors.append(f"PWA contract modes must match: {modes}")
        return errors
    pwa_mode = next(iter(modes.values()))
    evidence_mode = evidence.get("mode")
    if pwa_mode not in {"template", "planning", "product"}:
        return [f"unsupported PWA mode: {pwa_mode!r}"]
    if evidence_mode != pwa_mode:
        errors.append(
            f"PWA contract mode {pwa_mode!r} requires implementation-evidence mode {pwa_mode!r}; found {evidence_mode!r}"
        )
        return errors
    if pwa_mode == "template":
        return errors

    routes, route_errors = indexed(routes_document.get("routes"), collection="routes")
    surfaces, surface_errors = indexed(surfaces_document.get("surfaces"), collection="surfaces")
    states, state_errors = indexed(states_document.get("states"), collection="UI states")
    errors.extend(route_errors)
    errors.extend(surface_errors)
    errors.extend(state_errors)
    errors.extend(validate_manifest(manifest, routes))
    errors.extend(validate_offline(offline, manifest, routes, surfaces, states))
    errors.extend(validate_update(update, states))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        errors = validate(root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate PWA contracts: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    mode = load_json(root, PWA_MANIFEST).get("mode")
    if mode == "template":
        print("PWA contracts: template mode OK; no product PWA claim is active")
    elif mode == "planning":
        print("PWA planning semantics and Webapp cross-contract references: OK")
    else:
        print("PWA product semantics and Webapp cross-contract references: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
