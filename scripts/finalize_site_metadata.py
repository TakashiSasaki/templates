#!/usr/bin/env python3
"""Normalize deployment metadata in generated HTML before Pages upload."""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


LINK_TAG_PATTERN = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)
HEAD_CLOSE_PATTERN = re.compile(r"</head\s*>", re.IGNORECASE)
HREF_ATTRIBUTE_PATTERN = re.compile(
    r"(?<![-:\w])href\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
MANIFEST_HREF = "/app.webmanifest"
THEME_COLOR = "#3f51b5"


class SiteMetadataError(RuntimeError):
    """Raised when generated HTML metadata is ambiguous or cannot be normalized."""


class HeadElementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str | None]] = []
        self.metas: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        if tag.lower() == "link":
            self.links.append(attributes)
        elif tag.lower() == "meta":
            self.metas.append(attributes)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--canonical-url", required=True)
    return parser.parse_args()


def validate_canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.path.endswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise SiteMetadataError(
            "canonical URL must be an HTTPS directory URL without query or fragment"
        )
    return value


def parse_head_elements(source: str) -> HeadElementParser:
    parser = HeadElementParser()
    parser.feed(source)
    parser.close()
    return parser


def canonical_links(source: str) -> list[dict[str, str | None]]:
    return [
        link
        for link in parse_head_elements(source).links
        if "canonical" in (link.get("rel") or "").lower().split()
    ]


def manifest_links(source: str) -> list[dict[str, str | None]]:
    return [
        link
        for link in parse_head_elements(source).links
        if "manifest" in (link.get("rel") or "").lower().split()
    ]


def theme_color_metas(source: str) -> list[dict[str, str | None]]:
    return [
        meta
        for meta in parse_head_elements(source).metas
        if (meta.get("name") or "").casefold() == "theme-color"
    ]


def rewrite_canonical_link(source: str, canonical_url: str, path: Path) -> str:
    canonical_tags: list[str] = []
    for match in LINK_TAG_PATTERN.finditer(source):
        tag = match.group(0)
        if canonical_links(tag):
            canonical_tags.append(tag)
    if len(canonical_tags) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one canonical link, found {len(canonical_tags)}"
        )

    escaped_url = html.escape(canonical_url, quote=True)
    if not canonical_tags:
        head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
        if len(head_closes) != 1:
            raise SiteMetadataError(
                f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
            )
        insertion = f'<link rel="canonical" href="{escaped_url}">\n'
        position = head_closes[0].start()
        updated = source[:position] + insertion + source[position:]
    else:

        def replace_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            if not canonical_links(tag):
                return tag
            replacement = f'href="{escaped_url}"'
            if HREF_ATTRIBUTE_PATTERN.search(tag) is not None:
                return HREF_ATTRIBUTE_PATTERN.sub(replacement, tag, count=1)
            closing = "/>" if tag.endswith("/>") else ">"
            return tag[: -len(closing)] + " " + replacement + closing

        updated = LINK_TAG_PATTERN.sub(replace_tag, source)

    links = canonical_links(updated)
    if len(links) != 1 or links[0].get("href") != canonical_url:
        raise SiteMetadataError(f"{path}: canonical URL normalization failed")
    return updated


def ensure_pwa_metadata(source: str, path: Path) -> str:
    manifests = manifest_links(source)
    if len(manifests) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one web app manifest link, found {len(manifests)}"
        )
    if manifests and manifests[0].get("href") != MANIFEST_HREF:
        raise SiteMetadataError(
            f"{path}: web app manifest link must target {MANIFEST_HREF}"
        )

    themes = theme_color_metas(source)
    if len(themes) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one theme-color meta element, found {len(themes)}"
        )
    if themes and themes[0].get("content") != THEME_COLOR:
        raise SiteMetadataError(f"{path}: theme-color must be {THEME_COLOR}")

    additions: list[str] = []
    if not manifests:
        additions.append(f'<link rel="manifest" href="{MANIFEST_HREF}">\n')
    if not themes:
        additions.append(f'<meta name="theme-color" content="{THEME_COLOR}">\n')
    if not additions:
        return source

    head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
    if len(head_closes) != 1:
        raise SiteMetadataError(
            f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
        )
    position = head_closes[0].start()
    updated = source[:position] + "".join(additions) + source[position:]

    updated_manifests = manifest_links(updated)
    updated_themes = theme_color_metas(updated)
    if (
        len(updated_manifests) != 1
        or updated_manifests[0].get("href") != MANIFEST_HREF
        or len(updated_themes) != 1
        or updated_themes[0].get("content") != THEME_COLOR
    ):
        raise SiteMetadataError(f"{path}: PWA metadata normalization failed")
    return updated


def generated_html_files(site_root: Path) -> tuple[Path, list[Path]]:
    resolved_root = site_root.resolve(strict=True)
    html_files = sorted(
        path for path in resolved_root.rglob("*.html") if path.is_file()
    )
    if not html_files:
        raise SiteMetadataError(f"no generated HTML files found under {resolved_root}")
    return resolved_root, html_files


def is_inline_preview(path: Path, site_root: Path) -> bool:
    relative = path.relative_to(site_root)
    return relative.parts[:2] == ("repository-trees", "previews")


def normalize_canonical_links(site_root: Path, canonical_url: str) -> int:
    canonical_url = validate_canonical_url(canonical_url)
    _, html_files = generated_html_files(site_root)

    updates: dict[Path, str] = {}
    for path in html_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SiteMetadataError(f"unable to read generated HTML {path}: {exc}") from exc
        updates[path] = rewrite_canonical_link(source, canonical_url, path)

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(updates)


def normalize_site_metadata(
    site_root: Path,
    canonical_url: str,
) -> tuple[int, int]:
    canonical_url = validate_canonical_url(canonical_url)
    resolved_root, html_files = generated_html_files(site_root)

    updates: dict[Path, str] = {}
    pwa_pages = 0
    for path in html_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SiteMetadataError(f"unable to read generated HTML {path}: {exc}") from exc
        updated = rewrite_canonical_link(source, canonical_url, path)
        if not is_inline_preview(path, resolved_root):
            updated = ensure_pwa_metadata(updated, path)
            pwa_pages += 1
        updates[path] = updated

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(updates), pwa_pages


def main() -> int:
    args = parse_args()
    try:
        canonical_count, pwa_count = normalize_site_metadata(
            args.site_root,
            args.canonical_url,
        )
    except (OSError, SiteMetadataError) as exc:
        print(f"finalize_site_metadata.py: {exc}", file=sys.stderr)
        return 1
    print(
        f"normalized canonical URL in {canonical_count} generated HTML file(s) "
        f"and PWA metadata in {pwa_count} installable page(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
