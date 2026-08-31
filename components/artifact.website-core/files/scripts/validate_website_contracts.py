#!/usr/bin/env python3
"""Validate Website-owned contracts against shared Web route authority."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VISUALLY_BLANK_CHARACTERS = {"\u2800", "\U00013441", "\U00013442", "\U0001D159"}
HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


def load(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def has_visible_character(value: object) -> bool:
    return isinstance(value, str) and any(
        character not in VISUALLY_BLANK_CHARACTERS
        and unicodedata.category(character)[0] not in {"C", "M", "Z"}
        for character in value
    )


def valid_https_origin(value: object) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return False
    if port is not None and not 1 <= port <= 65535:
        return False
    host = parsed.hostname
    if not isinstance(host, str):
        return False
    normalized = host[:-1] if host.endswith(".") else host
    if not normalized or len(normalized) > 253:
        return False
    labels = normalized.split(".")
    return all(1 <= len(label) <= 63 and HOST_LABEL.fullmatch(label) for label in labels)


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
    viewports_doc = load(root, "contracts/viewports.json")
    evidence = load(root, "contracts/implementation-evidence.json")
    errors: list[str] = []

    routes = routes_doc.get("routes")
    route_list = [item for item in routes if isinstance(item, dict)] if isinstance(routes, list) else []
    route_ids = [item.get("id") for item in route_list if isinstance(item.get("id"), str)]
    route_set = set(route_ids)
    for duplicate in duplicates(route_ids):
        errors.append(f"duplicate shared Website route id: {duplicate}")
    canonical_paths = [item["path"] for item in route_list if isinstance(item.get("path"), str)]
    aliases = [alias for item in route_list for alias in item.get("aliases", []) if isinstance(item.get("aliases"), list) and isinstance(alias, str)]
    for duplicate in duplicates(canonical_paths):
        errors.append(f"duplicate shared Website canonical route path: {duplicate}")
    for duplicate in duplicates(aliases):
        errors.append(f"duplicate shared Website route alias: {duplicate}")
    for collision in sorted(set(canonical_paths) & set(aliases)):
        errors.append(f"shared Website route alias collides with canonical route path: {collision}")

    viewports = viewports_doc.get("viewports")
    viewport_list = [item for item in viewports if isinstance(item, dict)] if isinstance(viewports, list) else []
    viewport_ids = [item.get("id") for item in viewport_list if isinstance(item.get("id"), str)]
    for duplicate in duplicates(viewport_ids):
        errors.append(f"duplicate shared Website viewport id: {duplicate}")
    widths = [item.get("minWidthPx") for item in viewport_list if isinstance(item.get("minWidthPx"), int) and not isinstance(item.get("minWidthPx"), bool)]
    if widths and widths[0] != 0:
        errors.append("shared Website viewport breakpoints must start at minWidthPx 0")
    if any(current >= following for current, following in zip(widths, widths[1:])):
        errors.append("shared Website viewport breakpoints must be strictly increasing by minWidthPx")

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

    if not has_visible_character(metadata.get("siteName")):
        errors.append("Website siteName must contain at least one visible character")
    metadata_pages = metadata.get("pages")
    metadata_list = [item for item in metadata_pages if isinstance(item, dict)] if isinstance(metadata_pages, list) else []
    metadata_ids = [item.get("pageId") for item in metadata_list if isinstance(item.get("pageId"), str)]
    for duplicate in duplicates(metadata_ids):
        errors.append(f"duplicate Website document metadata pageId: {duplicate}")
    for item in metadata_list:
        page_id = item.get("pageId")
        for field in ("title", "description"):
            if not has_visible_character(item.get(field)):
                errors.append(f"Website document metadata {page_id!r} {field} must contain at least one visible character")
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

    robots = discovery.get("robots")
    robots_path = robots.get("path") if isinstance(robots, dict) else None
    sitemap_path = sitemap.get("path") if isinstance(sitemap, dict) else None
    if isinstance(robots_path, str) and robots_path == sitemap_path:
        errors.append(f"Website robots and sitemap discovery paths must be distinct: {robots_path!r}")

    feeds = discovery.get("feeds")
    feed_list = [item for item in feeds if isinstance(item, dict)] if isinstance(feeds, list) else []
    for field in ("id", "path"):
        values = [item[field] for item in feed_list if isinstance(item.get(field), str)]
        for duplicate in duplicates(values):
            errors.append(f"duplicate Website discovery feed {field}: {duplicate}")
    reserved_paths = {robots_path, sitemap_path}
    for feed in feed_list:
        if feed.get("path") in reserved_paths:
            errors.append(f"Website feed path collides with robots/sitemap discovery path: {feed.get('path')!r}")

    if evidence.get("mode") == "product" and not valid_https_origin(discovery.get("canonicalOrigin")):
        errors.append("Website product mode requires a concrete valid HTTPS canonicalOrigin")
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
    print("Website structure, document metadata, discovery, shared-route, and viewport invariants: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
