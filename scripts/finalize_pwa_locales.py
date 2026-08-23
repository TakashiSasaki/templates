#!/usr/bin/env python3
"""Inject locale-bound PWA freshness strings into generated PWA HTML."""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from site_chrome_locales import (
    SITE_CHROME_LOCALES,
    SiteChromeLocaleError,
    load_site_chrome_locales,
    pwa_freshness_strings,
)

MANIFEST_HREF = "/app.webmanifest"
LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
HEAD_CLOSE_PATTERN = re.compile(r"</head\s*>", re.IGNORECASE)
PWA_META_NAMES = {
    "saved_copy": "templates-pwa-saved-copy",
    "checking": "templates-pwa-checking",
    "unverified": "templates-pwa-unverified",
    "update_available": "templates-pwa-update-available",
    "published_changed": "templates-pwa-published-changed",
    "reload": "templates-pwa-reload",
}


class PwaLocaleFinalizeError(RuntimeError):
    """Raised when generated PWA locale metadata is malformed or ambiguous."""


class PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_languages: list[list[str | None]] = []
        self.manifest_hrefs: list[str | None] = []
        self.pwa_meta_names: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "html":
            self.html_languages.append(
                [value for name, value in attrs if name.casefold() == "lang"]
            )
            return
        if lowered == "link":
            rels = [value for name, value in attrs if name.casefold() == "rel"]
            hrefs = [value for name, value in attrs if name.casefold() == "href"]
            if any(
                isinstance(value, str)
                and "manifest" in {part.casefold() for part in value.split()}
                for value in rels
            ):
                self.manifest_hrefs.extend(hrefs or [None])
            return
        if lowered == "meta":
            names = [value for name, value in attrs if name.casefold() == "name"]
            for value in names:
                if isinstance(value, str) and value in PWA_META_NAMES.values():
                    self.pwa_meta_names.append(value)


def page_language_if_pwa(source: str, path: Path) -> str | None:
    parser = PageMetadataParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception as exc:
        raise PwaLocaleFinalizeError(f"{path}: unable to parse generated HTML: {exc}") from exc

    if not parser.manifest_hrefs:
        return None
    if parser.manifest_hrefs != [MANIFEST_HREF]:
        raise PwaLocaleFinalizeError(
            f"{path}: expected exactly one {MANIFEST_HREF} manifest reference"
        )
    if len(parser.html_languages) != 1 or len(parser.html_languages[0]) != 1:
        raise PwaLocaleFinalizeError(
            f"{path}: PWA page must contain exactly one html lang attribute"
        )
    language = parser.html_languages[0][0]
    if not isinstance(language, str) or not LANGUAGE_TAG.fullmatch(language):
        raise PwaLocaleFinalizeError(
            f"{path}: PWA page html lang must be a lowercase language tag"
        )
    if parser.pwa_meta_names:
        raise PwaLocaleFinalizeError(
            f"{path}: PWA freshness locale metadata already exists"
        )
    return language


def inject_pwa_locale_metadata(
    source: str,
    path: Path,
    strings: dict[str, str],
) -> str:
    if set(strings) != set(PWA_META_NAMES):
        raise PwaLocaleFinalizeError(
            f"{path}: PWA freshness strings do not match the metadata contract"
        )
    closes = list(HEAD_CLOSE_PATTERN.finditer(source))
    if len(closes) != 1:
        raise PwaLocaleFinalizeError(
            f"{path}: expected exactly one closing head tag, found {len(closes)}"
        )
    tags = "".join(
        f'<meta name="{html.escape(PWA_META_NAMES[field], quote=True)}" '
        f'content="{html.escape(quote(strings[field], safe=""), quote=True)}">\n'
        for field in PWA_META_NAMES
    )
    position = closes[0].start()
    return source[:position] + tags + source[position:]


def localize_pwa_source(
    source: str,
    path: Path,
    chrome: dict[str, object],
) -> tuple[str, bool]:
    language = page_language_if_pwa(source, path)
    if language is None:
        return source, False
    strings = pwa_freshness_strings(chrome, language)
    return inject_pwa_locale_metadata(source, path, strings), True


def finalize(
    site_root: Path,
    chrome_path: Path = SITE_CHROME_LOCALES,
) -> int:
    root = site_root.resolve(strict=True)
    chrome = load_site_chrome_locales(chrome_path)
    updates: dict[Path, str] = {}

    for path in sorted(root.rglob("*.html")):
        if path.is_symlink() or not path.is_file():
            raise PwaLocaleFinalizeError(f"generated HTML must be a regular file: {path}")
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PwaLocaleFinalizeError(f"unable to read generated HTML {path}: {exc}") from exc
        localized, changed = localize_pwa_source(source, path, chrome)
        if changed:
            updates[path] = localized

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(updates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument(
        "--site-chrome-locales",
        type=Path,
        default=SITE_CHROME_LOCALES,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        count = finalize(args.site_root, args.site_chrome_locales)
    except (
        OSError,
        UnicodeError,
        SiteChromeLocaleError,
        PwaLocaleFinalizeError,
    ) as exc:
        print(f"finalize_pwa_locales.py: {exc}", file=sys.stderr)
        return 1
    print(f"PWA locale metadata finalized: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
