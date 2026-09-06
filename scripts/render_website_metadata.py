#!/usr/bin/env python3
"""Apply Site-owned Website metadata to the built primary publication pages."""
import argparse
import html
import json
import re
from pathlib import Path


def render(repository: Path, site_root: Path) -> None:
    def load(name):
        return json.loads((repository / "contracts" / f"{name}.json").read_text())
    routes = {r["id"]: r["path"] for r in load("routes")["routes"]}
    pages = {p["id"]: p for p in load("site-structure")["pages"]}
    for meta in load("document-metadata")["pages"]:
        route = routes[pages[meta["pageId"]]["routeId"]]
        path = site_root / route.lstrip("/") / "index.html"
        source = path.read_text()
        source, count = re.subn(r"<title>.*?</title>", "<title>" + html.escape(meta["title"]) + "</title>", source, flags=re.S)
        if count != 1:
            raise ValueError(f"expected one title: {path}")
        # Zensical owns HTML rendering; Site's explicit product worksheet owns
        # the primary page metadata values. No provider document bytes change.
        source = re.sub(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>', "", source)
        marker = '<meta name="description" content="' + html.escape(meta["description"], quote=True) + '">'
        if source.lower().count("</head>") != 1:
            raise ValueError(f"expected one head: {path}")
        source = source.replace("</head>", marker + "</head>")
        path.write_text(source)
    (site_root / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + load("site-discovery")["canonicalOrigin"] + "/sitemap.xml\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    args = parser.parse_args()
    render(args.repository, args.site_root)
