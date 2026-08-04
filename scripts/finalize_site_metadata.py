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


class SiteMetadataError(RuntimeError):
    """Raised when generated HTML metadata is ambiguous or cannot be normalized."""


class LinkElementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() == "link":
            self.links.append({name.lower(): value for name, value in attrs})

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


def canonical_links(source: str) -> list[dict[str, str | None]]:
    parser = LinkElementParser()
    parser.feed(source)
    parser.close()
    return [
        link
        for link in parser.links
        if "canonical" in (link.get("rel") or "").lower().split()
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


def normalize_canonical_links(site_root: Path, canonical_url: str) -> int:
    canonical_url = validate_canonical_url(canonical_url)
    site_root = site_root.resolve(strict=True)
    html_files = sorted(path for path in site_root.rglob("*.html") if path.is_file())
    if not html_files:
        raise SiteMetadataError(f"no generated HTML files found under {site_root}")

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


def main() -> int:
    args = parse_args()
    try:
        count = normalize_canonical_links(args.site_root, args.canonical_url)
    except (OSError, SiteMetadataError) as exc:
        print(f"finalize_site_metadata.py: {exc}", file=sys.stderr)
        return 1
    print(f"normalized canonical URL in {count} generated HTML file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
