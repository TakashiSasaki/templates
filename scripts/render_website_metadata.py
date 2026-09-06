#!/usr/bin/env python3
"""Apply Site-owned Website metadata to the built primary publication pages."""
import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path


LINK_TAG_PATTERN = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.attributes = None

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "link":
            self.attributes = {name.casefold(): value for name, value in attrs}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def link_attributes(tag):
    parser = LinkParser()
    parser.feed(tag)
    parser.close()
    return parser.attributes or {}


def render_link(identity):
    attributes = [
        ("rel", identity["relation"]),
        ("href", identity["href"]),
    ]
    if "mediaType" in identity:
        attributes.append(("type", identity["mediaType"]))
    if "sizes" in identity:
        attributes.append(("sizes", " ".join(identity["sizes"])))
    return "<link " + " ".join(
        f'{name}="{html.escape(value, quote=True)}"' for name, value in attributes
    ) + ">"


def normalize_link_relation(source, relation, identities, path):
    relation = relation.casefold()

    def keep_or_remove(match):
        attributes = link_attributes(match.group(0))
        relations = (attributes.get("rel") or "").casefold().split()
        return "" if relation in relations else match.group(0)

    source = LINK_TAG_PATTERN.sub(keep_or_remove, source)
    if source.lower().count("</head>") != 1:
        raise ValueError(f"expected one head: {path}")
    markup = "".join(render_link(identity) for identity in identities)
    return source.replace("</head>", markup + "</head>")


def normalize_browser_identity(site_root, browser_identity, ios_identity):
    favicon_identities = [
        browser_identity,
        *(
            {**fallback, "relation": browser_identity["relation"]}
            for fallback in browser_identity["fallbacks"]
        ),
    ]
    for path in sorted(site_root.rglob("*.html")):
        source = path.read_text()
        source = normalize_link_relation(
            source,
            browser_identity["relation"],
            favicon_identities,
            path,
        )
        source = normalize_link_relation(
            source,
            ios_identity["relation"],
            [ios_identity],
            path,
        )
        path.write_text(source)


def render(repository: Path, site_root: Path) -> None:
    def load(name):
        return json.loads((repository / "contracts" / f"{name}.json").read_text())

    routes = {r["id"]: r["path"] for r in load("routes")["routes"]}
    pages = {p["id"]: p for p in load("site-structure")["pages"]}
    browser_identity = load("browser-identity")["favicon"]
    pwa = load("pwa-manifest")
    ios_identity = pwa["platformCompatibility"]["ios"]["homeScreenIcon"]

    for meta in load("document-metadata")["pages"]:
        route = routes[pages[meta["pageId"]]["routeId"]]
        path = site_root / route.lstrip("/") / "index.html"
        source = path.read_text()
        source, count = re.subn(r"<title>.*?</title>", "<title>" + html.escape(meta["title"]) + "</title>", source, flags=re.S)
        if count != 1:
            raise ValueError(f"expected one title: {path}")
        source = re.sub(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>', "", source)
        marker = '<meta name="description" content="' + html.escape(meta["description"], quote=True) + '">'
        if source.lower().count("</head>") != 1:
            raise ValueError(f"expected one head: {path}")
        source = source.replace("</head>", marker + "</head>")
        path.write_text(source)

    # Zensical owns HTML rendering; Site's explicit product worksheets own the
    # product-wide browser identity values. Normalize every generated HTML
    # document from those public contracts so localized, guided and repository
    # reader surfaces cannot silently retain framework-default link metadata.
    normalize_browser_identity(site_root, browser_identity, ios_identity)
    (site_root / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + load("site-discovery")["canonicalOrigin"] + "/sitemap.xml\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    args = parser.parse_args()
    render(args.repository, args.site_root)
