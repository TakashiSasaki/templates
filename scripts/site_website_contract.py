#!/usr/bin/env python3
"""Project Site's publication navigation into consumer-owned Website worksheets.

This is Site product code, not a Composition resolver or consumer-state manager.
It never writes provider-managed files, a lock, or Policy state.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path


def read(root: Path, path: str):
    return json.loads((root / path).read_text())


def leaves(items):
    for item in items:
        if "children" in item:
            yield from leaves(item["children"])
        elif "destination" in item:
            yield item


def public_path(destination: str) -> str:
    path = Path(destination)
    if path.name == "index.md":
        parent = path.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return "/" + path.with_suffix("").as_posix() + "/"


def documents(root: Path) -> dict:
    import tomllib
    project = tomllib.loads((root / "zensical.template.toml").read_text().replace("__GENERATED_NAV__", "[]"))["project"]
    navigation = list(leaves(read(root, "site-manifest.json")["navigation"]))
    pages, routes, metadata = [], [], []
    seen = set()
    for item in navigation:
        identity = item["publication"] + "-" + item["document"]
        if identity in seen:
            raise ValueError(f"duplicate Site document: {identity}")
        seen.add(identity)
        path = public_path(item["destination"])
        home = path == "/"
        routes.append({"id": identity, "path": path, "canonical": True, "aliases": [], "deepLink": True,
                       "accessibility": {"documentTitleRequired": True, "focusTarget": "main-heading"}})
        pages.append({"id": identity, "routeId": identity, "role": "home" if home else "content",
                      "title": item["title"], "parentPageId": None if home else "site-portal-home"})
        metadata.append({"pageId": identity, "title": item["title"],
                         "description": project["site_description"], "indexability": "index",
                         "canonicalPathPolicy": "route-canonical", "socialPreview": "none"})
    def doc(name, **values):
        return {"$schema": f"../schemas/{name}.schema.json", "schemaVersion": 1, **values}
    result = {
        "routes": {**doc("routes", routes=routes), "schemaVersion": 5},
        "site-structure": doc("site-structure", homePageId="site-portal-home", pages=pages,
                              primaryNavigationPageIds=[p["id"] for p in pages]),
        "document-metadata": doc("document-metadata", siteName=project["site_name"], defaultLanguage="en",
                                 siteSocialPreview="none", pages=metadata),
        "site-discovery": doc("site-discovery", canonicalOrigin=project["site_url"].rstrip("/"),
                              robots={"path":"/robots.txt","policy":"match-document-indexability"},
                              sitemap={"path":"/sitemap.xml","pageIds":[p["id"] for p in pages]}, feeds=[]),
    }
    return {f"contracts/{name}.json": value for name, value in result.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    stale = False
    for path, value in documents(args.repository).items():
        content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        target = args.repository / path
        if args.write:
            target.write_text(content)
        elif target.read_text() != content:
            stale = True
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            print(f"BEGIN_CANONICAL {path}")
            print(encoded)
            print(f"END_CANONICAL {path}")
    if stale:
        raise SystemExit("Site worksheet drift; run scripts/site_website_contract.py --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
