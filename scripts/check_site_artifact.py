#!/usr/bin/env python3
"""Validate active Site output and immutable source-link projections."""
from __future__ import annotations

import argparse
import html
import json
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from site_renderer.bundle import load_lock, validate_locked
from site_renderer.github import FULL_SHA
from site_renderer.guided import (
    edge_href,
    index_page_path,
    project_immutable_source_links,
)
from site_renderer.progressive_discovery import project, validate_generated


REPOSITORY = "TakashiSasaki/templates"
RETIRED_ROUTES = ("/files", "/repository-trees")
PUBLIC_SITE_ORIGIN = "https://templates.moukaeritai.work"
PUBLIC_SITE_HOST = urlsplit(PUBLIC_SITE_ORIGIN).netloc
GITHUB_HOST = "github.com"


class SiteArtifactError(ValueError):
    """Raised when generated Site output violates an active artifact contract."""


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._anchor: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        href = attributes.get("href")
        if href is not None:
            self.hrefs.append(href)
        if tag.lower() == "a" and href is not None:
            self._anchor = (href, [])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() == "a":
            self._finish_anchor()

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._anchor is not None:
            self._anchor[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._finish_anchor()

    def _finish_anchor(self) -> None:
        if self._anchor is not None:
            href, text = self._anchor
            self.anchors.append((href, "".join(text)))
            self._anchor = None


def _parse_html(path: Path) -> LinkParser:
    parser = LinkParser()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
    except (OSError, UnicodeError) as exc:
        raise SiteArtifactError(f"unable to read generated HTML {path}: {exc}") from exc
    return parser


def _is_retired_route(href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.netloc and parsed.netloc != PUBLIC_SITE_HOST:
        return None
    if parsed.scheme and not parsed.netloc:
        return None
    path = unquote(parsed.path)
    for route in RETIRED_ROUTES:
        if path == route or path.startswith(route + "/"):
            return route
    return None


def _validate_github_href(href: str, path: Path) -> None:
    parsed = urlsplit(href)
    if parsed.scheme != "https" or parsed.netloc != GITHUB_HOST:
        return
    parts = parsed.path.split("/")
    if len(parts) < 5 or "/".join(parts[1:3]) != REPOSITORY:
        return
    kind, revision = parts[3], parts[4]
    if kind not in {"commit", "blob", "tree"}:
        return
    if FULL_SHA.fullmatch(revision) is None:
        raise SiteArtifactError(
            f"{path}: canonical GitHub {kind} URL is not bound to a full SHA: {href}"
        )
    if kind == "commit" and len(parts) != 5:
        raise SiteArtifactError(f"{path}: commit URL contains a source path: {href}")
    if kind == "blob" and len(parts) < 6:
        raise SiteArtifactError(f"{path}: blob URL is missing its source path: {href}")
    if any(not segment for segment in parts[5:]):
        raise SiteArtifactError(f"{path}: GitHub source path contains an empty segment: {href}")


def _validate_provenance_links(
    site_root: Path,
    anchors: list[tuple[str, str]],
    rendered_text: str,
) -> None:
    provenance_path = site_root / "build-provenance.json"
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SiteArtifactError(f"invalid build provenance: {exc}") from exc
    try:
        revisions = {
            "site": provenance["site_commit"],
            "integration": provenance["integration"]["producer"]["revision"],
            **provenance["integration"]["providers"],
        }
    except (KeyError, TypeError) as exc:
        raise SiteArtifactError("build provenance is missing authority revisions") from exc
    if any(FULL_SHA.fullmatch(value or "") is None for value in revisions.values()):
        raise SiteArtifactError("build provenance contains a non-immutable authority revision")

    for authority, revision in revisions.items():
        if revision not in html.unescape(rendered_text):
            continue
        expected = f"https://github.com/{REPOSITORY}/commit/{revision}"
        if not any(revision in html.unescape(text) and href == expected for href, text in anchors):
            raise SiteArtifactError(
                f"provenance revision for {authority} is not linked to its commit page"
            )


def _validate_guided_projection(site_root: Path, bundle: Path, lock: dict) -> None:
    from scripts.check_bundle_reader import check as check_bundle_reader

    check_bundle_reader(site_root, bundle, lock)
    graph = project_immutable_source_links(
        json.loads((bundle / "guided-navigation.json").read_text(encoding="utf-8"))
    )
    documents = json.loads((bundle / "documents.json").read_text(encoding="utf-8"))
    published: dict[str, dict[str, str]] = {provider["name"]: {} for provider in graph["providers"]}
    for document in documents:
        if not document["slot"]:
            published.setdefault(document["publication"], {})[document["source"]] = document["destination"]

    for provider in graph["providers"]:
        for index in provider["indexes"]:
            page = site_root / index_page_path(provider["name"], index["path"])
            try:
                source = page.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise SiteArtifactError(f"missing guided page {page}: {exc}") from exc
            for edge in [edge for edge in provider["edges"] if edge["source"] == index["path"]]:
                href, _kind, _external = edge_href(
                    provider["name"], provider["revision"], edge, published[provider["name"]], graph["repository"]
                )
                escaped = html.escape(href, quote=True)
                if f'href="{escaped}"' not in source:
                    raise SiteArtifactError(f"guided edge projection missing from {page}: {href}")


def check(site_root: Path, bundle: Path | None = None, lock: dict | None = None) -> dict[str, int]:
    site_root = Path(site_root)
    if not site_root.is_dir():
        raise SiteArtifactError(f"generated Site root is not a directory: {site_root}")
    for route in RETIRED_ROUTES:
        target = site_root / route.lstrip("/")
        if target.exists() or target.is_symlink():
            raise SiteArtifactError(f"retired route was generated: {target}")

    html_files = sorted(site_root.rglob("*.html"))
    if not html_files:
        raise SiteArtifactError("generated Site contains no HTML files")
    try:
        validate_generated(site_root / "index.md")
    except (OSError, UnicodeError, ValueError) as exc:
        raise SiteArtifactError(
            f"static progressive discovery entry point is invalid: {exc}"
        ) from exc
    hrefs: list[str] = []
    anchors: list[tuple[str, str]] = []
    rendered_text: list[str] = []
    for path in html_files:
        parser = _parse_html(path)
        hrefs.extend(parser.hrefs)
        anchors.extend(parser.anchors)
        rendered_text.extend(parser.text_parts)
        for href in parser.hrefs:
            retired = _is_retired_route(href)
            if retired:
                raise SiteArtifactError(f"active HTML link points to retired route {retired}: {path}")
            _validate_github_href(href, path)
    _validate_provenance_links(site_root, anchors, "".join(rendered_text))
    if not any('data-playground-material-tree' in path.read_text(encoding="utf-8") for path in html_files):
        raise SiteArtifactError("Composition Playground material tree is missing")
    if bundle is not None:
        if lock is None:
            raise SiteArtifactError("Bundle validation requires the exact Site lock")
        validate_locked(bundle, lock)
        _validate_guided_projection(site_root, bundle, lock)
        source_root = Path(__file__).resolve().parents[1]
        try:
            expected = project(
                json.loads((source_root / "progressive-discovery.json").read_text()),
                json.loads((bundle / "guided-navigation.json").read_text()),
                json.loads((bundle / "documents.json").read_text()),
                site_catalog=json.loads((source_root / "docs/publication-catalog.json").read_text()),
            )
            validate_generated(site_root / "index.md", expected=expected)
        except (OSError, ValueError) as exc:
            raise SiteArtifactError(f"static progressive discovery is stale: {exc}") from exc
    return {
        "html_pages": len(html_files),
        "links": len(hrefs),
        "retired_route_links": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--lock", type=Path, default=Path("integration-source.json"))
    args = parser.parse_args()
    try:
        result = check(args.site_root, args.bundle, load_lock(args.lock) if args.bundle else None)
    except (OSError, SiteArtifactError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
