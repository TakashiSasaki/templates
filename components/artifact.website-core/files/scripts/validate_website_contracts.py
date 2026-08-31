#!/usr/bin/env python3
"""Validate Website-owned contracts against shared Web route authority."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def hierarchy_cycles(parents: dict[str, str | None]) -> list[list[str]]:
    cycles: list[list[str]] = []
    done: set[str] = set()
    for start in parents:
        if start in done:
            continue
        order: list[str] = []
        index: dict[str, int] = {}
        current: str | None = start
        while current is not None and current in parents and current not in done:
            if current in index:
                cycles.append(order[index[current]:] + [current])
                break
            index[current] = len(order)
            order.append(current)
            current = parents[current]
        done.update(order)
    return cycles


def validate(root: Path) -> list[str]:
    structure = load(root, "contracts/site-structure.json")
    metadata = load(root, "contracts/document-metadata.json")
    discovery = load(root, "contracts/site-discovery.json")
    routes_doc = load(root, "contracts/routes.json")
    evidence = load(root, "contracts/implementation-evidence.json")
    errors: list[str] = []

    routes = routes_doc.get("routes")
    route_ids = [item.get("id") for item in routes if isinstance(item, dict) and isinstance(item.get("id"), str)] if isinstance(routes, list) else []
    route_set = set(route_ids)
    for duplicate in duplicates(route_ids):
        errors.append(f"duplicate shared Website route id: {duplicate}")

    pages = structure.get("pages")
    page_list = [item for item in pages if isinstance(item, dict)] if isinstance(pages, list) else []
    page_ids = [item.get("id") for item in page_list if isinstance(item.get("id"), str)]
    page_route_ids = [item.get("routeId") for item in page_list if isinstance(item.get("routeId"), str)]
    for duplicate in duplicates(page_ids):
        errors.append(f"duplicate Website page id: {duplicate}")
    for duplicate in duplicates(page_route_ids):
        errors.append(f"multiple Website pages bind shared route: {duplicate}")
    page_by_id = {item["id"]: item for item in page_list if isinstance(item.get("id"), str)}
    page_set = set(page_ids)
    if set(page_route_ids) != route_set:
        missing = sorted(route_set - set(page_route_ids))
        unknown = sorted(set(page_route_ids) - route_set)
        if missing:
            errors.append(f"shared Website routes are missing page bindings: {missing}")
        if unknown:
            errors.append(f"Website pages reference unknown shared routes: {unknown}")

    home_id = structure.get("homePageId")
    home = page_by_id.get(home_id) if isinstance(home_id, str) else None
    if home is None:
        errors.append(f"Website homePageId references unknown page: {home_id!r}")
    else:
        if home.get("role") != "home":
            errors.append("Website homePageId must reference the page with role 'home'")
        if home.get("parentPageId") is not None:
            errors.append("Website home page must not have a parentPageId")
    home_roles = [item.get("id") for item in page_list if item.get("role") == "home"]
    if len(home_roles) != 1:
        errors.append(f"Website structure must declare exactly one home-role page; found {home_roles}")

    parents: dict[str, str | None] = {}
    for page in page_list:
        page_id = page.get("id")
        if not isinstance(page_id, str):
            continue
        parent = page.get("parentPageId")
        if parent is not None and parent not in page_set:
            errors.append(f"Website page {page_id!r} references unknown parentPageId {parent!r}")
        if page_id != home_id and parent is None:
            errors.append(f"Website non-home page {page_id!r} must declare a parentPageId")
        parents[page_id] = parent if isinstance(parent, str) else None
    for cycle in hierarchy_cycles(parents):
        errors.append(f"Website page hierarchy contains a cycle: {' -> '.join(cycle)}")

    navigation = structure.get("primaryNavigationPageIds")
    if isinstance(navigation, list):
        for page_id in navigation:
            if isinstance(page_id, str) and page_id not in page_set:
                errors.append(f"primary navigation references unknown Website page {page_id!r}")

    metadata_pages = metadata.get("pages")
    metadata_list = [item for item in metadata_pages if isinstance(item, dict)] if isinstance(metadata_pages, list) else []
    metadata_ids = [item.get("pageId") for item in metadata_list if isinstance(item.get("pageId"), str)]
    for duplicate in duplicates(metadata_ids):
        errors.append(f"duplicate Website document metadata pageId: {duplicate}")
    if set(metadata_ids) != page_set:
        missing = sorted(page_set - set(metadata_ids))
        extra = sorted(set(metadata_ids) - page_set)
        if missing:
            errors.append(f"Website pages are missing document metadata: {missing}")
        if extra:
            errors.append(f"document metadata references unknown Website pages: {extra}")
    if metadata.get("siteSocialPreview") == "none":
        inherited = sorted(item.get("pageId") for item in metadata_list if item.get("socialPreview") == "inherit-site")
        if inherited:
            errors.append(f"pages cannot inherit social preview when siteSocialPreview is none: {inherited}")

    indexable = {item["pageId"] for item in metadata_list if isinstance(item.get("pageId"), str) and item.get("indexability") == "index"}
    sitemap = discovery.get("sitemap")
    sitemap_ids = set(sitemap.get("pageIds", [])) if isinstance(sitemap, dict) and isinstance(sitemap.get("pageIds"), list) else set()
    if sitemap_ids != indexable:
        errors.append(f"Website sitemap pageIds must exactly match indexable document metadata pages; expected {sorted(indexable)}, found {sorted(sitemap_ids)}")

    feeds = discovery.get("feeds")
    feed_list = [item for item in feeds if isinstance(item, dict)] if isinstance(feeds, list) else []
    for field in ("id", "path"):
        values = [item[field] for item in feed_list if isinstance(item.get(field), str)]
        for duplicate in duplicates(values):
            errors.append(f"duplicate Website discovery feed {field}: {duplicate}")
    reserved_paths = {
        discovery.get("robots", {}).get("path") if isinstance(discovery.get("robots"), dict) else None,
        sitemap.get("path") if isinstance(sitemap, dict) else None,
    }
    for feed in feed_list:
        if feed.get("path") in reserved_paths:
            errors.append(f"Website feed path collides with robots/sitemap discovery path: {feed.get('path')!r}")

    if evidence.get("mode") == "product" and not isinstance(discovery.get("canonicalOrigin"), str):
        errors.append("Website product mode requires a concrete HTTPS canonicalOrigin")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    try:
        errors = validate(Path(args.root).resolve())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate Website contracts: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Website structure, document metadata, discovery, and shared-route bindings: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
