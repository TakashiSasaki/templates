#!/usr/bin/env python3
"""Validate artifact-neutral Progressive Web App semantics against shared Web routes."""
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
    if scope == "/":
        return path.startswith("/")
    scope_root = scope.rstrip("/")
    return path == scope_root or path.startswith(scope)


def validate_manifest(manifest: dict[str, Any], routes: dict[str, dict[str, Any]]) -> list[str]:
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
                errors.append(f"PWA start route {route_id!r} path {path!r} is outside manifest scope {scope!r}")

    icons = manifest.get("icons")
    icon_list = [icon for icon in icons if isinstance(icon, dict)] if isinstance(icons, list) else []
    icon_ids = [icon.get("id") for icon in icon_list if isinstance(icon.get("id"), str)]
    icon_hrefs = [icon.get("href") for icon in icon_list if isinstance(icon.get("href"), str)]
    for duplicate, count in sorted(Counter(icon_ids).items()):
        if count > 1:
            errors.append(f"duplicate PWA manifest icon id: {duplicate}")
    for duplicate, count in sorted(Counter(icon_hrefs).items()):
        if count > 1:
            errors.append(f"duplicate PWA manifest icon href: {duplicate}")

    svg_icons = [icon for icon in icon_list if icon.get("mediaType") == "image/svg+xml"]
    vector_exception = manifest.get("vectorIconException")
    if manifest.get("vectorIconPolicy") == "prefer-svg-when-compatible":
        if not svg_icons and not isinstance(vector_exception, str):
            errors.append("PWA vector icon policy prefers SVG when compatible; declare an SVG manifest icon or a non-blank vectorIconException")
        if svg_icons and isinstance(vector_exception, str):
            errors.append("PWA vectorIconException must be null when an SVG manifest icon is declared")

    compatibility = manifest.get("platformCompatibility")
    android = compatibility.get("android") if isinstance(compatibility, dict) else None
    ios = compatibility.get("ios") if isinstance(compatibility, dict) else None
    if isinstance(android, dict):
        required_sizes = android.get("requiredRasterSizes")
        if isinstance(required_sizes, list):
            for required_size in required_sizes:
                covered = any(
                    icon.get("mediaType") != "image/svg+xml"
                    and isinstance(icon.get("sizes"), list)
                    and required_size in icon["sizes"]
                    for icon in icon_list
                )
                if not covered:
                    errors.append(f"Android compatibility raster size {required_size!r} is not backed by a declared non-SVG manifest icon")
        if android.get("maskableIconRequired") is True and not any(
            isinstance(icon.get("purposes"), list) and "maskable" in icon["purposes"]
            for icon in icon_list
        ):
            errors.append("Android compatibility requires at least one maskable manifest icon")

    home_icon = ios.get("homeScreenIcon") if isinstance(ios, dict) else None
    if isinstance(home_icon, dict) and home_icon.get("mediaType") == "image/svg+xml":
        errors.append("iOS home-screen compatibility icon must provide raster artwork rather than SVG-only artwork")
    return errors


def validate_offline(offline: dict[str, Any], manifest: dict[str, Any], routes: dict[str, dict[str, Any]]) -> list[str]:
    if offline.get("availability") != "offline-capable":
        return ["selected PWA planning/product semantics must be offline-capable so network loss has an intentional caller-visible presentation instead of a broken page"]

    errors: list[str] = []
    controlled = offline.get("controlledRouteIds")
    controlled_ids = {item for item in controlled if isinstance(item, str)} if isinstance(controlled, list) else set()
    service_scope = offline.get("serviceWorkerScope")
    manifest_scope = manifest.get("scope")
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
                errors.append(f"PWA controlled route {route_id!r} path {path!r} is outside serviceWorkerScope {service_scope!r}")
            if isinstance(path, str) and isinstance(manifest_scope, str) and not path_in_scope(path, manifest_scope):
                errors.append(f"PWA controlled route {route_id!r} path {path!r} is outside manifest scope {manifest_scope!r}")

    fallback = offline.get("navigationFallbackRouteId")
    if isinstance(fallback, str):
        if fallback not in routes:
            errors.append(f"PWA navigationFallbackRouteId references unknown route {fallback!r}")
        elif fallback not in controlled_ids:
            errors.append("PWA navigation fallback route must be included in controlledRouteIds")

    policies = offline.get("routePolicies")
    policy_ids: list[str] = []
    if isinstance(policies, list):
        for policy in policies:
            if not isinstance(policy, dict) or not isinstance(policy.get("routeId"), str):
                continue
            route_id = policy["routeId"]
            policy_ids.append(route_id)
            if route_id not in routes:
                errors.append(f"PWA offline route policy references unknown route {route_id!r}")
    for duplicate, count in sorted(Counter(policy_ids).items()):
        if count > 1:
            errors.append(f"duplicate PWA offline route policy: {duplicate}")
    policy_set = set(policy_ids)
    missing = sorted(controlled_ids - policy_set)
    extra = sorted(policy_set - controlled_ids)
    if missing:
        errors.append(f"PWA controlled routes are missing explicit offline route policies: {missing}")
    if extra:
        errors.append(f"PWA offline route policies do not belong to controlled routes: {extra}")
    return errors


def validate_update(update: dict[str, Any]) -> list[str]:
    if update.get("activation") == "immediate" and update.get("unsavedChangesPolicy") == "block-activation":
        return ["immediate PWA update activation cannot use block-activation unsavedChangesPolicy"]
    return []


def validate(root: Path) -> list[str]:
    manifest = load_json(root, PWA_MANIFEST)
    offline = load_json(root, PWA_OFFLINE)
    update = load_json(root, PWA_UPDATE)
    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)

    modes = {
        "pwa-manifest": manifest.get("mode"),
        "pwa-offline": offline.get("mode"),
        "pwa-update": update.get("mode"),
    }
    if len(set(modes.values())) != 1:
        return [f"PWA contract modes must match: {modes}"]
    pwa_mode = next(iter(modes.values()))
    evidence_mode = evidence.get("mode")
    if pwa_mode not in {"template", "planning", "product"}:
        return [f"unsupported PWA mode: {pwa_mode!r}"]
    if evidence_mode != pwa_mode:
        return [f"PWA contract mode {pwa_mode!r} requires implementation-evidence mode {pwa_mode!r}; found {evidence_mode!r}"]
    if pwa_mode == "template":
        return []

    routes_document = load_json(root, ROUTES)
    routes, errors = indexed(routes_document.get("routes"), collection="routes")
    errors.extend(validate_manifest(manifest, routes))
    errors.extend(validate_offline(offline, manifest, routes))
    errors.extend(validate_update(update))
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
        print("PWA planning installability, route-scoped offline freshness, platform compatibility, and update semantics: OK")
    else:
        print("PWA product installability, route-scoped offline freshness, platform compatibility, and update semantics: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
